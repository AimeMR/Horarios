from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, CalendarBlock, Session, TimetableData
from horaris_solver.solver.phase1_time import Phase1Result, solve_phase1
from horaris_solver.solver.slots import day_from_index, slots_for_duration

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)
WEDNESDAY = date(2026, 9, 16)


def test_phase1_keeps_fixed_plab() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30)
    assert result.ok
    plab = data.activities["A4"]
    assert result.activity_day[plab.id] == data.sessions[plab.session_ids[0]].day
    assert result.activity_start[plab.id] == data.sessions[plab.session_ids[0]].start_min


def test_phase1_assigns_all_activities() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30)
    assert result.ok
    assert set(result.activity_day) == set(data.activities)


def test_phase1_accepts_hints_and_stops_after_first_feasible() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    hints = Phase1Result(
        True,
        {activity.id: data.sessions[activity.session_ids[0]].day for activity in data.activities.values()},
        {activity.id: data.sessions[activity.session_ids[0]].start_min for activity in data.activities.values()},
        "GREEDY",
        "partida as warm-start hints",
    )
    result = solve_phase1(
        data,
        max_time_s=30,
        hints=hints,
        stop_after_first_feasible=True,
    )
    assert result.ok
    assert result.status in {"OPTIMAL", "FEASIBLE"}


def _pair(
    aid: str,
    *,
    session_date: date = MONDAY,
    start: int = 9 * 60,
    duration: int = 60,
    turn: str = "mati",
    fixed: str = "",
    kind: str = "TE",
    teachers: frozenset[str] = frozenset(),
    group: str = "TE/11",
) -> tuple[Session, Activity]:
    session = Session(
        id=f"S_{aid}",
        activity_id=aid,
        code=f"C_{aid}",
        kind=kind,
        group=group,
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="",
        cohorts=(f"COH_{aid}",),
        turn=turn,
        fixed=fixed,
        teachers=teachers,
    )
    activity = Activity(
        id=aid,
        code=f"C_{aid}",
        kind=kind,
        session_ids=(session.id,),
        students=10,
        turn=turn,
        fixed=fixed,
        teachers=teachers,
        cohorts=(f"COH_{aid}",),
        duration_min=duration,
    )
    return session, activity


def _data(
    *pairs: tuple[Session, Activity],
    calendar: tuple[CalendarBlock, ...] = (),
    days_without_class: frozenset[date] = frozenset(),
) -> TimetableData:
    return TimetableData(
        sessions={s.id: s for s, _ in pairs},
        rooms={},
        activities={a.id: a for _, a in pairs},
        calendar=calendar,
        days_without_class=days_without_class,
    )


def test_movable_far_from_every_slot_is_placed() -> None:
    # Partida at 16:00 for a morning activity: every legal start is >= 90 min away (old delta domain was 0..48 min).
    data = _data(_pair("A", start=16 * 60))
    result = solve_phase1(data, max_time_s=10)
    assert result.ok, result.message
    assert result.activity_start["A"] in slots_for_duration(60, "mati")
    assert result.activity_day["A"] == "L"


@pytest.mark.parametrize(("fixed", "kind"), [("R1-FIXADA", "TE"), ("R7: PLAB", "PLAB")])
def test_pinned_out_of_turn_stays_at_partida(fixed: str, kind: str) -> None:
    data = _data(_pair("P", session_date=WEDNESDAY, start=16 * 60, fixed=fixed, kind=kind))
    result = solve_phase1(data, max_time_s=10)
    assert result.ok, result.message
    assert result.activity_day["P"] == "X"
    assert result.activity_start["P"] == 16 * 60


def test_pinned_pair_clashing_in_partida_is_not_infeasible() -> None:
    teacher = frozenset({"T1"})
    data = _data(
        _pair("P1", fixed="R1-FIXADA", teachers=teacher),
        _pair("P2", fixed="R1-FIXADA", teachers=teacher, group="TE/21"),
    )
    result = solve_phase1(data, max_time_s=10)
    assert result.ok, result.message
    assert result.activity_start == {"P1": 9 * 60, "P2": 9 * 60}


def test_movable_avoids_calendar_and_pinned_neighbour() -> None:
    teacher = frozenset({"T1"})
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4))  # Tue..Fri of the partida week
    aturada = CalendarBlock(MONDAY, 12 * 60, 14 * 60 + 30, "aturada")
    data = _data(
        _pair("P", fixed="R1-FIXADA", teachers=teacher),
        _pair("M", teachers=teacher, group="TE/21"),
        calendar=(aturada,),
        days_without_class=closed,
    )
    result = solve_phase1(data, max_time_s=10)
    assert result.ok, result.message
    assert result.activity_day["M"] == "L"
    assert result.activity_start["M"] in {10 * 60, 10 * 60 + 30, 11 * 60}


def test_empty_domain_returns_infeasible_data() -> None:
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4)) | {date(2026, 9, 21)}
    session_a, activity = _pair("E")
    session_b = replace(session_a, id="S_E2", session_date=date(2026, 9, 22), day="M")
    activity = replace(activity, session_ids=(session_a.id, session_b.id))
    data = TimetableData(
        sessions={session_a.id: session_a, session_b.id: session_b},
        rooms={},
        activities={activity.id: activity},
        days_without_class=closed,
    )
    result = solve_phase1(data, max_time_s=5)
    assert not result.ok
    assert result.status == "INFEASIBLE_DATA"
    assert "E" in result.message


def test_random_seed_and_workers_are_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, int]] = []

    original_solve = cp_model.CpSolver.Solve

    def _recording_solve(self: cp_model.CpSolver, model: cp_model.CpModel, *args: object, **kwargs: object) -> object:
        seen.append((self.parameters.random_seed, self.parameters.num_search_workers))
        return original_solve(self, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "Solve", _recording_solve)
    data = _data(_pair("A"))
    result = solve_phase1(data, max_time_s=5, random_seed=1234, num_workers=1)
    assert result.ok
    assert seen == [(1234, 1)]


# --- inherited partida overlaps (F1) ------------------------------------------------------------

_FULL_MORNING = 6 * 60
_MORNING_START = 8 * 60 + 30
_CLOSED_REST_OF_WEEK = frozenset(date(2026, 9, 15 + i) for i in range(4))


def _squeeze(second_start: int) -> TimetableData:
    """Two full-morning activities sharing a teacher whose only legal slot is Monday 08:30."""
    teacher = frozenset({"T1"})
    return _data(
        _pair("A", start=_MORNING_START, duration=_FULL_MORNING, teachers=teacher),
        _pair("B", start=second_start, duration=_FULL_MORNING, teachers=teacher, group="TE/21"),
        days_without_class=_CLOSED_REST_OF_WEEK,
    )


def test_inherited_overlap_in_squeeze_is_feasible() -> None:
    result = solve_phase1(_squeeze(_MORNING_START), max_time_s=10)
    assert result.ok, result.message
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.activity_start == {"A": _MORNING_START, "B": _MORNING_START}


def test_non_inherited_overlap_in_squeeze_is_still_infeasible() -> None:
    result = solve_phase1(_squeeze(15 * 60), max_time_s=10)
    assert not result.ok
    assert result.status == "INFEASIBLE"


def test_inherited_overlap_is_penalised_and_removed_when_possible() -> None:
    teacher = frozenset({"T1"})
    data = _data(
        _pair("A", teachers=teacher),
        _pair("B", start=9 * 60 + 30, teachers=teacher, group="TE/21"),
    )
    result = solve_phase1(data, max_time_s=10)
    assert result.ok, result.message
    starts = sorted(result.activity_start.values())
    same_day = result.activity_day["A"] == result.activity_day["B"]
    assert not same_day or starts[1] - starts[0] >= 60


def test_soft_overlap_relaxes_an_infeasible_squeeze() -> None:
    result = solve_phase1(_squeeze(15 * 60), max_time_s=10, soft_overlap=True)
    assert result.ok, result.message
    assert result.status == "RELAXED_R4"
    assert "1 overlapping pair" in result.message
    assert "A" not in result.message.split(":")[-1]


def test_soft_overlap_without_remaining_overlap_keeps_solver_status() -> None:
    teacher = frozenset({"T1"})
    data = _data(_pair("A", teachers=teacher), _pair("B", start=11 * 60, teachers=teacher, group="TE/21"))
    result = solve_phase1(data, max_time_s=10, soft_overlap=True)
    assert result.ok, result.message
    assert result.status in {"OPTIMAL", "FEASIBLE"}


def test_mini_paquet_objective_unchanged_by_soft_overlap_flag() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    plain = solve_phase1(data, max_time_s=30, num_workers=1, random_seed=0)
    relaxed = solve_phase1(data, max_time_s=30, num_workers=1, random_seed=0, soft_overlap=True)
    assert plain.ok and relaxed.ok
    assert relaxed.status in {"OPTIMAL", "FEASIBLE"}
    assert relaxed.objective == plain.objective
