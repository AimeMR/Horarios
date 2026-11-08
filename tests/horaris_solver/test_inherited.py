from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, Session, TimetableData
from horaris_solver.solver.calendar_rules import overlaps
from horaris_solver.solver.conflicts import activities_interact
from horaris_solver.solver.inherited import is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.slots import day_from_index

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)
TEACHER = frozenset({"T1"})


def _pair(
    aid: str,
    *,
    session_date: date = MONDAY,
    start: int = 9 * 60,
    duration: int = 60,
    teachers: frozenset[str] = TEACHER,
    shared_id: str = "",
) -> tuple[Session, Activity]:
    session = Session(
        id=f"S-{aid}",
        activity_id=aid,
        code=f"C-{aid}",
        kind="TE",
        group=f"TE/{aid}",
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="",
        cohorts=(f"COH-{aid}",),
        turn="mati",
        fixed="",
        teachers=teachers,
        shared_id=shared_id,
    )
    activity = Activity(
        id=aid,
        code=session.code,
        kind="TE",
        session_ids=(session.id,),
        students=10,
        turn="mati",
        fixed="",
        teachers=teachers,
        cohorts=session.cohorts,
        duration_min=duration,
    )
    return session, activity


def _data(*pairs: tuple[Session, Activity]) -> TimetableData:
    return TimetableData(
        sessions={s.id: s for s, _ in pairs},
        rooms={},
        activities={a.id: a for _, a in pairs},
    )


def test_overlapping_interacting_pair_is_inherited() -> None:
    data = _data(_pair("B", start=9 * 60 + 30), _pair("A"))
    pairs = partida_overlap_pairs(data)
    assert pairs == frozenset({("A", "B")})
    assert is_inherited_pair(pairs, "A", "B")
    assert is_inherited_pair(pairs, "B", "A")


def test_touching_sessions_are_not_inherited() -> None:
    data = _data(_pair("A"), _pair("B", start=10 * 60))
    assert partida_overlap_pairs(data) == frozenset()


def test_non_interacting_overlap_is_not_inherited() -> None:
    data = _data(_pair("A", teachers=frozenset({"T1"})), _pair("B", teachers=frozenset({"T2"})))
    assert partida_overlap_pairs(data) == frozenset()


def test_same_time_on_another_date_is_not_inherited() -> None:
    data = _data(_pair("A"), _pair("B", session_date=MONDAY + timedelta(days=7)))
    assert partida_overlap_pairs(data) == frozenset()


def test_same_teaching_event_is_not_inherited() -> None:
    data = _data(_pair("A", shared_id="X"), _pair("B", shared_id="X"))
    assert partida_overlap_pairs(data) == frozenset()


def test_sweep_finds_pair_past_a_short_session() -> None:
    long_a = _pair("A", start=8 * 60 + 30, duration=240)
    short = _pair("S", start=9 * 60, duration=30, teachers=frozenset({"OTHER"}))
    late = _pair("C", start=11 * 60)
    pairs = partida_overlap_pairs(_data(long_a, short, late))
    assert pairs == frozenset({("A", "C")})


def test_unknown_pair_is_not_inherited() -> None:
    assert not is_inherited_pair(frozenset({("A", "B")}), "A", "C")


def test_mini_paquet_pairs_match_brute_force() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    expected: set[tuple[str, str]] = set()
    sessions = [s for s in data.sessions.values() if s.activity_id in data.activities]
    for i, left in enumerate(sessions):
        for right in sessions[i + 1 :]:
            if left.activity_id == right.activity_id or left.session_date != right.session_date:
                continue
            if not overlaps(left.start_min, left.duration_min, right.start_min, right.duration_min):
                continue
            a, b = data.activities[left.activity_id], data.activities[right.activity_id]
            if activities_interact(a, b, data):
                low, high = sorted((a.id, b.id))
                expected.add((low, high))
    pairs = partida_overlap_pairs(data)
    assert pairs == frozenset(expected)
    assert all(low < high for low, high in pairs)
