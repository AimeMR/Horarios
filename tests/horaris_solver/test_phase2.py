from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Assignment, Room, Session, TimetableData
from horaris_solver.solver import phase2_rooms
from horaris_solver.solver.phase1_time import expand_phase1_to_assignments, solve_phase1
from horaris_solver.solver.phase2_rooms import Phase2Result, solve_phase2
from horaris_solver.solver.room_rules import room_candidates, unit_students
from horaris_solver.solver.rules import activity_pools

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_phase2_assigns_rooms_and_keeps_plab() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    phase1 = solve_phase1(data, max_time_s=30)
    assert phase1.ok
    timed = expand_phase1_to_assignments(data, phase1)
    phase2 = solve_phase2(data, timed, max_time_s=30)
    assert phase2.ok
    by_id = {a.session_id: a for a in phase2.assignments}
    assert by_id["S00005"].room == "Q5/0001"
    for sid, assignment in by_id.items():
        session = data.sessions[sid]
        if session.sense_espai:
            continue
        assert assignment.room


SEMINAR_ROOMS = {
    "A/1001": Room("A/1001", "A", "Seminaris", 60),
    "A/1999": Room("A/1999", "A", "Seminaris", 60),
    "B/2001": Room("B/2001", "B", "Seminaris", 60),
    "J/1001": Room("J/1001", "J", "Seminaris", 60),
}


def _session(
    sid: str,
    kind: str,
    *,
    start: int,
    partida: str,
    cohort: str,
    group: str,
    fixed: str = "",
    sense: bool = False,
) -> Session:
    return Session(
        id=sid,
        activity_id=f"act_{sid}",
        code="101",
        kind=kind,
        group=group,
        session_date=date(2026, 2, 2),
        day="L",
        start_min=start,
        duration_min=60,
        students=10,
        room_partida=partida,
        cohorts=(cohort,),
        turn="mati",
        fixed=fixed,
        teachers=frozenset(),
        sense_espai=sense,
    )


def _contested(r1_partida: str = "A/1001", *, sense: bool = False) -> tuple[TimetableData, list[Assignment]]:
    """R1 session X competes for A/1001 with Y, which would rather stay next to its PAUL Z."""
    sessions = [
        _session("X", "TE", start=600, partida=r1_partida, cohort="C1", group="1", fixed="R1", sense=sense),
        _session("Y", "TE", start=600, partida="A/1001", cohort="C2", group="2"),
        _session("Z", "PAUL", start=630, partida="A/1999", cohort="C2", group="2"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=SEMINAR_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    return data, timed


def _rooms(result: Phase2Result) -> dict[str, str]:
    return {a.session_id: a.room for a in result.assignments}


def test_phase2_r1_keeps_partida_room() -> None:
    data, timed = _contested()
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["X"] == "A/1001"
    assert rooms["Y"] != "A/1001"


def test_phase2_r1_in_j_room_is_not_pinned() -> None:
    data, timed = _contested("J/1001")
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    assert _rooms(result)["X"] in SEMINAR_ROOMS


def test_phase2_r1_sense_espai_gets_no_room() -> None:
    data, timed = _contested(sense=True)
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["X"] == ""
    assert rooms["Y"] == "A/1001"


def test_phase2_r1_without_partida_gets_a_room() -> None:
    data, timed = _contested("")
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    assert _rooms(result)["X"] in SEMINAR_ROOMS


def test_phase2_r1_moved_day_is_not_pinned() -> None:
    data, timed = _contested()
    timed = [replace(a, day="M") if a.session_id == "X" else a for a in timed]
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    assert _rooms(result)["X"] in SEMINAR_ROOMS


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize("max_time_s", [1.0, 10.0, 150.0])
def test_phase2_two_attempts_never_exceed_budget(monkeypatch: pytest.MonkeyPatch, max_time_s: float) -> None:
    clock = _FakeClock()
    calls: list[tuple[float, bool]] = []

    def fake_solve_rooms(
        data: TimetableData, timed: dict[str, Assignment], *, max_time_s: float, soft_r8: bool
    ) -> Phase2Result:
        calls.append((max_time_s, soft_r8))
        clock.now += max_time_s
        return Phase2Result(soft_r8, [], "FEASIBLE" if soft_r8 else "INFEASIBLE", "fake", soft_r8)

    monkeypatch.setattr(phase2_rooms, "_clock", clock)
    monkeypatch.setattr(phase2_rooms, "_solve_rooms", fake_solve_rooms)
    data, timed = _contested()
    result = solve_phase2(data, timed, max_time_s=max_time_s)

    assert result.ok and result.r8_relaxed
    assert [soft for _, soft in calls] == [False, True]
    assert calls[0][0] == pytest.approx(0.5 * max_time_s)
    assert calls[1][0] == pytest.approx(0.25 * max_time_s)
    assert sum(t for t, _ in calls) <= max_time_s + 1e-9


def test_phase2_fallback_gets_only_time_left(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock()
    calls: list[float] = []

    def slow_strict(
        data: TimetableData, timed: dict[str, Assignment], *, max_time_s: float, soft_r8: bool
    ) -> Phase2Result:
        calls.append(max_time_s)
        clock.now += 0.9 * 100.0 if not soft_r8 else max_time_s
        return Phase2Result(soft_r8, [], "X", "fake", soft_r8)

    monkeypatch.setattr(phase2_rooms, "_clock", clock)
    monkeypatch.setattr(phase2_rooms, "_solve_rooms", slow_strict)
    data, timed = _contested()
    solve_phase2(data, timed, max_time_s=100.0)

    assert calls[0] == pytest.approx(50.0)
    assert calls[1] == pytest.approx(5.0)


def test_phase2_no_fallback_runs_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_solve_rooms(
        data: TimetableData, timed: dict[str, Assignment], *, max_time_s: float, soft_r8: bool
    ) -> Phase2Result:
        calls.append(max_time_s)
        return Phase2Result(False, [], "INFEASIBLE", "fake", soft_r8)

    monkeypatch.setattr(phase2_rooms, "_solve_rooms", fake_solve_rooms)
    data, timed = _contested()
    result = solve_phase2(data, timed, max_time_s=10.0, r8_soft_fallback=False)

    assert not result.ok
    assert calls == [pytest.approx(10.0)]


def _pinned_pair(fixed: str, *, with_movable: bool = False) -> tuple[TimetableData, list[Assignment]]:
    """Two pinned sessions overlap in partida in the same room (an inherited R4-AULA)."""
    sessions = [
        _session("P1", "TE", start=600, partida="A/1001", cohort="C1", group="1", fixed=fixed),
        _session("P2", "TE", start=630, partida="A/1001", cohort="C2", group="2", fixed=fixed),
    ]
    if with_movable:
        sessions.append(_session("M", "TE", start=600, partida="A/1001", cohort="C3", group="3"))
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=SEMINAR_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    return data, timed


@pytest.mark.parametrize("fixed", ["R1", "R7"])
def test_phase2_overlapping_pinned_sessions_share_partida_room(fixed: str) -> None:
    data, timed = _pinned_pair(fixed)
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["P1"] == "A/1001"
    assert rooms["P2"] == "A/1001"


@pytest.mark.parametrize("fixed", ["R1", "R7"])
def test_phase2_movable_session_still_leaves_pinned_room(fixed: str) -> None:
    data, timed = _pinned_pair(fixed, with_movable=True)
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["P1"] == rooms["P2"] == "A/1001"
    assert rooms["M"] not in {"A/1001", ""}


def test_phase2_pinned_r1_moved_time_still_not_double_booked() -> None:
    data, timed = _pinned_pair("R1")
    timed = [replace(a, start_min=610) if a.session_id == "P2" else a for a in timed]
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["P1"] == "A/1001"
    assert rooms["P2"] != "A/1001"


ORDINARY_ROOMS = {
    "O/1": Room("O/1", "O", "Aules docents", 60),
    "O/2": Room("O/2", "O", "Aules docents", 60),
    "O/3": Room("O/3", "O", "Aules docents", 60),
}


def test_phase2_pinned_occupancy_over_r8_reserve_is_inherited() -> None:
    sessions = [
        _session("P1", "TE", start=630, partida="O/1", cohort="C1", group="1", fixed="R1"),
        _session("P2", "TE", start=630, partida="O/2", cohort="C2", group="2", fixed="R7"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=ORDINARY_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    assert not result.r8_relaxed
    assert "r8_inherited=1" in result.message
    rooms = _rooms(result)
    assert rooms == {"P1": "O/1", "P2": "O/2"}


def test_phase2_r8_inherited_slot_blocks_more_ordinary_rooms() -> None:
    rooms = {**ORDINARY_ROOMS, "S/1": Room("S/1", "S", "Seminaris", 60)}
    sessions = [
        _session("P1", "TE", start=630, partida="O/1", cohort="C1", group="1", fixed="R1"),
        _session("P2", "TE", start=630, partida="O/2", cohort="C2", group="2", fixed="R7"),
        _session("M", "TE", start=630, partida="O/3", cohort="C3", group="3"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=rooms, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    assert "r8_inherited=1" in result.message
    assert _rooms(result) == {"P1": "O/1", "P2": "O/2", "M": "S/1"}


def test_phase2_r8_inherited_slot_infeasible_without_other_room() -> None:
    sessions = [
        _session("P1", "TE", start=630, partida="O/1", cohort="C1", group="1", fixed="R1"),
        _session("P2", "TE", start=630, partida="O/2", cohort="C2", group="2", fixed="R7"),
        _session("M", "TE", start=630, partida="O/3", cohort="C3", group="3"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=ORDINARY_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    assert not solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False).ok


def test_phase2_shared_unit_gets_room_fitting_sum() -> None:
    rooms = {"O/1": Room("O/1", "O", "Seminaris", 15), "O/2": Room("O/2", "O", "Seminaris", 25)}
    left = replace(
        _session("U1", "TE", start=600, partida="O/1", cohort="C1", group="1"),
        shared_id="U",
    )
    right = replace(left, id="U2", cohorts=("C2",))
    data = TimetableData(sessions={left.id: left, right.id: right}, rooms=rooms, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in (left, right)]
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert result.ok
    assert _rooms(result) == {"U1": "O/2", "U2": "O/2"}


def test_phase2_r7_plab_keeps_external_j_room_and_te_leaves_it() -> None:
    sessions = [
        _session("P", "PLAB", start=600, partida="J/012", cohort="C1", group="1", fixed="R7"),
        _session("T", "TE", start=600, partida="J/013", cohort="C2", group="2"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=SEMINAR_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["P"] == "J/012"
    assert rooms["T"] in SEMINAR_ROOMS
    assert not rooms["T"].startswith("J/")


def test_phase2_overlapping_r7_plabs_without_room_are_not_double_booked() -> None:
    sessions = [
        _session("P1", "PLAB", start=600, partida="", cohort="C1", group="1", fixed="R7"),
        _session("P2", "PLAB", start=600, partida="", cohort="C2", group="2", fixed="R7"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=SEMINAR_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    assert _rooms(result) == {"P1": "", "P2": ""}


def test_phase2_r8_still_strict_without_pinned_excess() -> None:
    sessions = [
        _session("A", "TE", start=600, partida="O/1", cohort="C1", group="1"),
        _session("B", "TE", start=600, partida="O/2", cohort="C2", group="2"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=ORDINARY_ROOMS, activities={})
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in sessions]
    result = solve_phase2(data, timed, max_time_s=10, r8_soft_fallback=False)
    assert not result.ok


TWO_SEMINARS = {
    "S/1": Room("S/1", "S", "Seminaris", 60),
    "S/2": Room("S/2", "S", "Seminaris", 60),
}


def _timed(sessions: list[Session]) -> list[Assignment]:
    return [Assignment(s.id, s.day, s.start_min, "") for s in sessions]


def test_phase2_partial_leaves_only_overflow_without_room() -> None:
    sessions = [_session(f"M{i}", "PAUL", start=600, partida="S/1", cohort=f"C{i}", group=str(i)) for i in range(3)]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=TWO_SEMINARS, activities={})
    result = solve_phase2(data, _timed(sessions), max_time_s=10)
    assert result.ok
    assert result.r8_relaxed
    assert len(result.unassigned) == 1
    assert result.message == "phase2 partial unassigned=1"
    rooms = _rooms(result)
    assert rooms[result.unassigned[0]] == ""
    placed = [room for sid, room in rooms.items() if sid not in result.unassigned]
    assert sorted(placed) == ["S/1", "S/2"]


def test_phase2_partial_never_unassigns_pinned_plab_or_r1() -> None:
    rooms = {"S/1": Room("S/1", "S", "Seminaris", 60), "L/1": Room("L/1", "L", "Laboratoris docents", 60)}
    sessions = [
        _session("X", "TE", start=600, partida="S/1", cohort="C1", group="1", fixed="R1"),
        _session("P", "PLAB", start=600, partida="L/1", cohort="C2", group="2", fixed="R7"),
        _session("M", "TE", start=600, partida="S/1", cohort="C3", group="3"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=rooms, activities={})
    result = solve_phase2(data, _timed(sessions), max_time_s=10)
    assert result.ok
    assert result.unassigned == ("M",)
    assert _rooms(result) == {"X": "S/1", "P": "L/1", "M": ""}


def test_phase2_feasible_instance_skips_partial_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    flags: list[bool] = []
    real = phase2_rooms._solve_rooms

    def spy(
        data: TimetableData,
        timed: dict[str, Assignment],
        *,
        max_time_s: float,
        soft_r8: bool,
        allow_unassigned: bool = False,
    ) -> Phase2Result:
        flags.append(allow_unassigned)
        return real(data, timed, max_time_s=max_time_s, soft_r8=soft_r8, allow_unassigned=allow_unassigned)

    monkeypatch.setattr(phase2_rooms, "_solve_rooms", spy)
    data, timed = _contested()
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    assert result.unassigned == ()
    assert True not in flags
    assert all(_rooms(result).values())


@pytest.mark.parametrize("max_time_s", [1.0, 10.0, 150.0])
def test_phase2_three_attempts_never_exceed_budget(monkeypatch: pytest.MonkeyPatch, max_time_s: float) -> None:
    clock = _FakeClock()
    calls: list[tuple[float, bool, bool]] = []

    def fake_solve_rooms(
        data: TimetableData,
        timed: dict[str, Assignment],
        *,
        max_time_s: float,
        soft_r8: bool,
        allow_unassigned: bool = False,
    ) -> Phase2Result:
        calls.append((max_time_s, soft_r8, allow_unassigned))
        clock.now += max_time_s
        if allow_unassigned:
            return Phase2Result(True, [], "FEASIBLE", "fake", True, unassigned=("a", "b"))
        return Phase2Result(False, [], "INFEASIBLE", "fake", soft_r8)

    monkeypatch.setattr(phase2_rooms, "_clock", clock)
    monkeypatch.setattr(phase2_rooms, "_solve_rooms", fake_solve_rooms)
    data, timed = _contested()
    result = solve_phase2(data, timed, max_time_s=max_time_s)

    assert result.ok and result.r8_relaxed
    assert result.unassigned == ("a", "b")
    assert result.message == "phase2 partial unassigned=2"
    assert [(soft, partial) for _, soft, partial in calls] == [(False, False), (True, False), (True, True)]
    assert calls[0][0] == pytest.approx(0.5 * max_time_s)
    assert calls[1][0] == pytest.approx(0.25 * max_time_s)
    assert calls[2][0] == pytest.approx(0.25 * max_time_s)
    assert sum(t for t, _, _ in calls) <= max_time_s + 1e-9


def test_phase2_overlapping_unassigned_sessions_stay_feasible() -> None:
    rooms = {"S/1": Room("S/1", "S", "Seminaris", 60)}
    sessions = [_session(f"M{i}", "TE", start=600, partida="S/1", cohort=f"C{i}", group=str(i)) for i in range(4)]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=rooms, activities={})
    result = solve_phase2(data, _timed(sessions), max_time_s=10)
    assert result.ok
    assert len(result.unassigned) == 3
    assert sorted(_rooms(result).values()) == ["", "", "", "S/1"]


def test_phase2_partial_leaves_session_without_any_valid_room_unassigned() -> None:
    rooms = {"S/1": Room("S/1", "S", "Seminaris", 60)}  # no lab-kind room for the PLAB
    sessions = [
        _session("T", "TE", start=600, partida="S/1", cohort="C1", group="1"),
        _session("Q", "PLAB", start=700, partida="", cohort="C2", group="2"),
    ]
    data = TimetableData(sessions={s.id: s for s in sessions}, rooms=rooms, activities={})
    result = solve_phase2(data, _timed(sessions), max_time_s=10)
    assert result.ok
    assert result.unassigned == ("Q",)
    assert _rooms(result) == {"T": "S/1", "Q": ""}


def _online_paquet(tmp_path: Path) -> Path:
    """Mini paquet with activity A1 renamed to the online activity A0826."""
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    for source in FIXTURE.iterdir():
        text = source.read_text(encoding="utf-8")
        if source.name == "sessions.csv":
            text = text.replace(",A1,", ",A0826,")
        (paquet / source.name).write_text(text, encoding="utf-8")
    return paquet


def test_a0826_sessions_get_real_room(tmp_path: Path) -> None:
    data = CsvTimetableSource(_online_paquet(tmp_path)).load()
    timed = [Assignment(s.id, s.day, s.start_min, "") for s in data.sessions.values()]
    result = solve_phase2(data, timed, max_time_s=10)
    assert result.ok
    rooms = _rooms(result)
    assert rooms["S00001"] != "" and rooms["S00002"] != ""
    assert "S00001" not in result.unassigned and "S00002" not in result.unassigned


def test_phase2_online_session_does_not_block_the_only_room() -> None:
    online = replace(_session("O", "TE", start=600, partida="A/1001", cohort="C1", group="1", sense=True), online=True)
    regular = _session("R", "TE", start=600, partida="A/1001", cohort="C2", group="2")
    rooms = {"A/1001": SEMINAR_ROOMS["A/1001"]}
    data = TimetableData(sessions={"O": online, "R": regular}, rooms=rooms, activities={})
    result = solve_phase2(data, _timed([online, regular]), max_time_s=10)
    assert result.ok and not result.unassigned
    assert _rooms(result) == {"O": "", "R": "A/1001"}
