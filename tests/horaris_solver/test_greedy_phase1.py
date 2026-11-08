from datetime import date
from pathlib import Path
from typing import Any

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, CalendarBlock, Session, TimetableData
from horaris_solver.solver import greedy_phase1
from horaris_solver.solver.calendar_rules import overlaps
from horaris_solver.solver.conflicts import activities_interact
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import Phase1Result, expand_phase1_to_assignments
from horaris_solver.solver.slots import day_index

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
_MONDAY = date(2026, 9, 14)
_TEACHER = frozenset({"TIGHT"})
_MORNING_START = 8 * 60 + 30
_FULL_MORNING = 6 * 60
_DAY_LETTERS = ("L", "M", "X", "J", "V")


def test_greedy_places_mini() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1_greedy(data)
    assert result.ok
    assert result.status == "GREEDY"
    assert set(result.activity_day) == set(data.activities)
    timed = expand_phase1_to_assignments(data, result)
    assert len(timed) == len(data.sessions)


def _tight_morning_data(count: int) -> TimetableData:
    """count full-morning same-teacher activities: only 5 weekday slots exist."""
    sessions: dict[str, Session] = {}
    activities: dict[str, Activity] = {}
    order: list[str] = []
    for index in range(count):
        activity_id = f"A{index}"
        session_id = f"S{index}"
        # Distinct partida slots (weekday mornings, then the afternoon) so no pair overlaps in partida.
        offset = index % 5
        sessions[session_id] = Session(
            id=session_id,
            activity_id=activity_id,
            code="TIGHT",
            kind="TE",
            group=f"TE/{index}1",
            session_date=date(2026, 9, 14 + offset),
            day=_DAY_LETTERS[offset],
            start_min=_MORNING_START if index < 5 else 15 * 60,
            duration_min=_FULL_MORNING,
            students=10,
            room_partida="",
            cohorts=("GEI:1r",),
            turn="mati",
            fixed="",
            teachers=_TEACHER,
        )
        activities[activity_id] = Activity(
            id=activity_id,
            code="TIGHT",
            kind="TE",
            session_ids=(session_id,),
            students=10,
            turn="mati",
            fixed="",
            teachers=_TEACHER,
            cohorts=("GEI:1r",),
            duration_min=_FULL_MORNING,
        )
        order.append(session_id)
    return TimetableData(
        sessions=sessions,
        rooms={},
        activities=activities,
        order=tuple(order),
    )


def test_greedy_keeps_partial_maps_when_unplaced() -> None:
    data = _tight_morning_data(6)
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY_PARTIAL"
    assert result.ok is False
    assert result.activity_day
    assert result.activity_start
    assert set(result.activity_day) == set(result.activity_start)
    assert set(result.activity_day) < set(data.activities)
    unplaced = result.unplaced
    assert unplaced
    assert set(unplaced).isdisjoint(result.activity_day)
    assert set(unplaced) | set(result.activity_day) == set(data.activities)


# --- regression helpers -------------------------------------------------------------------------


def _spec(
    activity_id: str,
    *,
    teacher: str,
    start: int = _MORNING_START,
    duration: int = _FULL_MORNING,
    day_offset: int = 0,
    fixed: str = "",
    shared_id: str = "",
    turn: str = "mati",
    kind: str = "TE",
) -> tuple[Session, Activity]:
    """One-session activity; each gets its own cohort/group so only teachers clash."""
    session_date = date(2026, 9, 14 + day_offset)
    session = Session(
        id=f"S-{activity_id}",
        activity_id=activity_id,
        code=f"C-{activity_id}",
        kind=kind,
        group=f"{kind}/{activity_id}",
        session_date=session_date,
        day=_DAY_LETTERS[day_offset],
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="",
        cohorts=(f"COH-{activity_id}",),
        turn=turn,
        fixed=fixed,
        teachers=frozenset({teacher}),
        shared_id=shared_id,
    )
    activity = Activity(
        id=activity_id,
        code=session.code,
        kind=kind,
        session_ids=(session.id,),
        students=10,
        turn=turn,
        fixed=fixed,
        teachers=session.teachers,
        cohorts=session.cohorts,
        duration_min=duration,
    )
    return session, activity


def _build(
    specs: list[tuple[Session, Activity]],
    *,
    calendar: tuple[CalendarBlock, ...] = (),
    days_without_class: frozenset[date] = frozenset(),
) -> TimetableData:
    return TimetableData(
        sessions={s.id: s for s, _ in specs},
        rooms={},
        activities={a.id: a for _, a in specs},
        calendar=calendar,
        days_without_class=days_without_class,
        order=tuple(s.id for s, _ in specs),
    )


def _no_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_repair(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)


def _placed_clashes(data: TimetableData, result: Phase1Result) -> list[tuple[str, str]]:
    ids = sorted(result.activity_day)
    hits: list[tuple[str, str]] = []
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1 :]:
            if result.activity_day[left_id] != result.activity_day[right_id]:
                continue
            left, right = data.activities[left_id], data.activities[right_id]
            if not activities_interact(left, right, data):
                continue
            if overlaps(
                result.activity_start[left_id],
                left.duration_min,
                result.activity_start[right_id],
                right.duration_min,
            ):
                hits.append((left_id, right_id))
    return hits


def _at_partida(data: TimetableData, result: Phase1Result, activity_id: str) -> bool:
    template = data.sessions[data.activities[activity_id].session_ids[0]]
    return (
        result.activity_day.get(activity_id) == template.day
        and result.activity_start.get(activity_id) == template.start_min
    )


# --- regressions --------------------------------------------------------------------------------


def test_shared_partner_with_teacher_clash_is_not_placed_onto_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    # BLOCK (teacher U, 2h at 9:00 Monday) is placed first (longest). A is free at 9:00 Monday,
    # but its shared partner B (teacher U) would clash with BLOCK there.
    data = _build(
        [
            _spec("BLOCK", teacher="U", start=9 * 60, duration=120),
            _spec("A", teacher="T", start=9 * 60, duration=60, shared_id="X"),
            _spec("B", teacher="U", start=9 * 60, duration=60, shared_id="X"),
        ]
    )
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert _placed_clashes(data, result) == []
    assert (result.activity_day["A"], result.activity_start["A"]) == (
        result.activity_day["B"],
        result.activity_start["B"],
    )


def test_shared_group_without_common_domain_is_left_unplaced(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    data = _build(
        [
            _spec("A", teacher="T", start=9 * 60, duration=60, shared_id="X", turn="mati"),
            _spec("B", teacher="U", start=16 * 60, duration=60, shared_id="X", turn="tarda"),
        ]
    )
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY_PARTIAL"
    assert set(result.unplaced) == {"A", "B"}
    assert result.activity_day == {}


def test_failed_displacement_restores_shared_partners(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    # Teacher T is busy every morning (T0..T4) and so is teacher U (U0..U4).
    # X (teacher T) and XP (teacher U) are shared: every displacement attempt must fail and roll back
    # completely, including XP, which must not be left on a slot it clashes with.
    specs = [_spec(f"T{d}", teacher="T", day_offset=d) for d in range(5)]
    specs += [_spec(f"U{d}", teacher="U", day_offset=d) for d in range(5)]
    specs += [
        _spec("X", teacher="T", shared_id="SH", start=15 * 60),
        _spec("XP", teacher="U", shared_id="SH", start=15 * 60),
    ]
    data = _build(specs)
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY_PARTIAL"
    assert set(result.unplaced) == {"X", "XP"}
    assert _placed_clashes(data, result) == []
    for d in range(5):
        assert _at_partida(data, result, f"T{d}")
        assert _at_partida(data, result, f"U{d}")


def test_greedy_skips_days_without_class_and_aturades(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    # PIN holds Monday morning for teacher T; Tuesday is a day without class; Wednesday morning is an
    # aturada. The movable activity must land on Thursday.
    tuesday, wednesday = date(2026, 9, 15), date(2026, 9, 16)
    data = _build(
        [
            _spec("PIN", teacher="T", fixed="R1-FIXADA"),
            _spec("A", teacher="T"),
        ],
        calendar=(CalendarBlock(wednesday, 8 * 60, 15 * 60, "aturada"),),
        days_without_class=frozenset({tuesday}),
    )
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert result.activity_day["A"] == "J"


def test_greedy_never_moves_r1_out_of_turn() -> None:
    data = _build([_spec("R1A", teacher="T", start=16 * 60, duration=60, fixed="R1-FIXADA", turn="mati")])
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert _at_partida(data, result, "R1A")
    assert result.objective == 0


def test_greedy_never_moves_r7_even_when_a_longer_activity_wants_its_slot() -> None:
    data = _build(
        [
            _spec("LONG", teacher="T", start=9 * 60, duration=180),
            _spec("LAB", teacher="T", start=9 * 60, duration=60, fixed="R7-PLAB", kind="PLAB"),
        ]
    )
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert _at_partida(data, result, "LAB")
    assert not _at_partida(data, result, "LONG")
    assert _placed_clashes(data, result) == []
    assert result.objective == 1


def test_clashing_pinned_pair_stays_at_partida_without_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    data = _build(
        [
            _spec("P1", teacher="T", fixed="R1-FIXADA"),
            _spec("P2", teacher="T", fixed="R7-PLAB", kind="PLAB"),
        ],
        days_without_class=frozenset(date(2026, 9, 15 + i) for i in range(4)),
    )
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert result.ok
    assert _at_partida(data, result, "P1")
    assert _at_partida(data, result, "P2")
    assert result.objective == 0


def test_pinned_blocker_is_never_displaced(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    # Teacher T has a pinned activity every morning; A cannot displace any of them.
    specs = [_spec(f"P{d}", teacher="T", day_offset=d, fixed="R1-FIXADA") for d in range(5)]
    specs.append(_spec("A", teacher="T", start=15 * 60))
    data = _build(specs)
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY_PARTIAL"
    assert result.unplaced == ("A",)
    for d in range(5):
        assert _at_partida(data, result, f"P{d}")


def test_repair_time_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_repair(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)
    result = solve_phase1_greedy(_tight_morning_data(6), repair_time_s=3.5)
    assert result.status == "GREEDY_PARTIAL"
    assert captured["max_time_s"] == 3.5


def test_default_repair_time_is_45s(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_repair(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)
    solve_phase1_greedy(_tight_morning_data(6))
    assert captured["max_time_s"] == 45.0


def test_partida_is_first_candidate_when_free() -> None:
    data = _build([_spec("A", teacher="T", start=10 * 60, duration=60, day_offset=2)])
    result = solve_phase1_greedy(data)
    assert result.status == "GREEDY"
    assert (day_index(result.activity_day["A"]), result.activity_start["A"]) == (2, 10 * 60)
    assert result.objective == 0


def test_greedy_places_inherited_pair_in_single_legal_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4))
    first = _spec("A", teacher="T")
    second = _spec("B", teacher="T")
    data = _build([first, second], days_without_class=closed)
    result = solve_phase1_greedy(data)
    assert result.ok, result.message
    assert result.activity_start == {"A": _MORNING_START, "B": _MORNING_START}


def test_greedy_still_blocks_non_inherited_clash_in_single_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4))
    first = _spec("A", teacher="T")
    second = _spec("B", teacher="T", start=15 * 60)
    data = _build([first, second], days_without_class=closed)
    result = solve_phase1_greedy(data)
    assert not result.ok
    assert result.status == "GREEDY_PARTIAL"


def test_repair_defaults_keep_unseeded_parallel_search(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_repair(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)
    solve_phase1_greedy(_tight_morning_data(6))
    assert captured["random_seed"] is None
    assert captured["deterministic"] is False


def test_seed_and_deterministic_are_forwarded_to_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_repair(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)
    result = solve_phase1_greedy(_tight_morning_data(6), seed=11, deterministic=True)
    assert result.status == "GREEDY_PARTIAL"
    assert captured["random_seed"] == 11
    assert captured["deterministic"] is True
