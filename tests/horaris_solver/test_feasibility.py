from datetime import date

from horaris_solver.domain.models import Activity, CalendarBlock, Session, TimetableData
from horaris_solver.solver.feasibility import allowed_days, allowed_starts, domain_values, is_pinned
from horaris_solver.solver.slots import day_from_index, slots_for_duration
from horaris_solver.solver.violations import Violation

MONDAY = date(2026, 9, 14)


def _session(sid: str, session_date: date, start: int, *, turn: str, fixed: str, duration: int = 60) -> Session:
    return Session(
        id=sid,
        activity_id="A1",
        code="C1",
        kind="TE",
        group="G/101",
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=duration,
        students=20,
        room_partida="R",
        cohorts=("C1-1",),
        turn=turn,
        fixed=fixed,
        teachers=frozenset(),
    )


def _data(
    *,
    turn: str = "mati",
    fixed: str = "",
    dates: tuple[date, ...] = (MONDAY,),
    start: int = 9 * 60,
    duration: int = 60,
    calendar: tuple[CalendarBlock, ...] = (),
    days_without_class: frozenset[date] = frozenset(),
) -> tuple[TimetableData, Activity]:
    sessions = {
        f"S{i}": _session(f"S{i}", d, start, turn=turn, fixed=fixed, duration=duration) for i, d in enumerate(dates)
    }
    activity = Activity(
        id="A1",
        code="C1",
        kind="TE",
        session_ids=tuple(sessions),
        students=20,
        turn=turn,
        fixed=fixed,
        teachers=frozenset(),
        cohorts=("C1-1",),
        duration_min=duration,
    )
    data = TimetableData(
        sessions=sessions,
        rooms={},
        activities={"A1": activity},
        calendar=calendar,
        days_without_class=days_without_class,
    )
    return data, activity


def test_violation_defaults() -> None:
    violation = Violation(rule="D1-TURN", activity_ids=("A1",))
    assert violation.detail == ""
    assert violation.activity_ids == ("A1",)


def test_is_pinned_for_r1_and_r7_only() -> None:
    assert is_pinned(_data(fixed="R1-FIXADA")[1])
    assert is_pinned(_data(fixed="R7-PLAB")[1])
    assert not is_pinned(_data(fixed="")[1])
    assert not is_pinned(_data(fixed="R3-OTHER")[1])
    assert not is_pinned(_data(fixed="X-R1")[1])


def test_r1_out_of_turn_stays_pinned_to_partida() -> None:
    # Partida at 16:00 on Wednesday although the activity turn is morning.
    wednesday = date(2026, 9, 16)
    data, activity = _data(turn="mati", fixed="R1-FIXADA", dates=(wednesday,), start=16 * 60)
    assert allowed_days(data, activity) == (2,)
    assert allowed_starts(data, activity, 2) == (16 * 60,)
    assert allowed_starts(data, activity, 0) == ()
    assert domain_values(data, activity) == ((2, 16 * 60),)


def test_r7_pinned_even_with_calendar_blocks() -> None:
    data, activity = _data(
        fixed="R7-PLAB",
        start=10 * 60,
        calendar=(CalendarBlock(MONDAY, 9 * 60, 12 * 60, "aturada"),),
    )
    assert domain_values(data, activity) == ((0, 10 * 60),)


def test_movable_excludes_day_without_class() -> None:
    thursday = date(2026, 9, 17)
    data, activity = _data(days_without_class=frozenset({thursday}))
    assert allowed_days(data, activity) == (0, 1, 2, 4)


def test_partida_date_on_day_without_class_is_not_forbidden() -> None:
    data, activity = _data(days_without_class=frozenset({MONDAY}))
    assert 0 in allowed_days(data, activity)


def test_allowed_days_can_be_empty() -> None:
    # Sessions on Monday (week 1) and Tuesday (week 2): every weekday moves at least one onto a closed day.
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4)) | {date(2026, 9, 21)}
    data, activity = _data(dates=(MONDAY, date(2026, 9, 22)), days_without_class=closed)
    assert allowed_days(data, activity) == ()
    assert domain_values(data, activity) == ()


def test_allowed_starts_excludes_aturada_overlap() -> None:
    tuesday = date(2026, 9, 15)
    data, activity = _data(calendar=(CalendarBlock(tuesday, 10 * 60, 11 * 60, "aturada"),))
    base = slots_for_duration(60, "mati")
    starts = allowed_starts(data, activity, 1)
    assert 10 * 60 not in starts
    assert 9 * 60 + 30 not in starts
    assert 10 * 60 + 30 not in starts
    assert 9 * 60 in starts
    assert 11 * 60 in starts
    assert starts == tuple(s for s in base if not (s < 11 * 60 and s + 60 > 10 * 60))
    assert allowed_starts(data, activity, 0) == tuple(base)


def test_aturada_on_any_session_week_applies() -> None:
    later_tuesday = date(2026, 9, 22)
    data, activity = _data(
        dates=(MONDAY, date(2026, 9, 21)),
        calendar=(CalendarBlock(later_tuesday, 8 * 60 + 30, 9 * 60 + 30, "aturada"),),
    )
    starts = allowed_starts(data, activity, 1)
    assert 8 * 60 + 30 not in starts
    assert 9 * 60 + 30 in starts


def test_domain_values_sorted_and_complete() -> None:
    friday = date(2026, 9, 18)
    data, activity = _data(days_without_class=frozenset({friday}))
    values = domain_values(data, activity)
    assert values == tuple(sorted(values))
    base = slots_for_duration(60, "mati")
    assert values == tuple((d, s) for d in range(4) for s in base)
