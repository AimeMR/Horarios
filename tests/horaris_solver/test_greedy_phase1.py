from datetime import date
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, Session, TimetableData
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import expand_phase1_to_assignments

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
_MONDAY = date(2026, 9, 14)
_TEACHER = frozenset({"TIGHT"})
_MORNING_START = 8 * 60 + 30
_FULL_MORNING = 6 * 60


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
        sessions[session_id] = Session(
            id=session_id,
            activity_id=activity_id,
            code="TIGHT",
            kind="TE",
            group=f"TE/{index}1",
            session_date=_MONDAY,
            day="L",
            start_min=_MORNING_START,
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
