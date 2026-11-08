from dataclasses import replace
from datetime import date
from typing import NamedTuple

import pytest
from ortools.sat.python import cp_model

from horaris_solver.domain.models import Activity, CalendarBlock, Session, TimetableData
from horaris_solver.solver import local_cpsat_repair as repair_mod
from horaris_solver.solver.local_cpsat_repair import blocking_neighborhood, repair_unplaced_with_cpsat
from horaris_solver.solver.slots import slots_for_duration

_MONDAY = date(2026, 9, 14)
_TEACHER = frozenset({"T_REPAIR"})
_UNPLACED_ID = "UNPLACED"
_LONG_ID = "LONG_BLOCKER"
_SHORT_COUNT = 90
_SHORT_DURATION = 30
_LONG_DURATION = 180
_START = 8 * 60 + 30


class _Neighborhood(NamedTuple):
    data: TimetableData
    placed: dict[str, tuple[int, int]]
    activity_day: dict[str, str]
    activity_start: dict[str, int]
    unplaced: list[str]
    long_id: str


def _session(
    *,
    sid: str,
    activity_id: str,
    duration_min: int,
    group: str,
) -> Session:
    return Session(
        id=sid,
        activity_id=activity_id,
        code="REP",
        kind="TE",
        group=group,
        session_date=_MONDAY,
        day="L",
        start_min=_START,
        duration_min=duration_min,
        students=10,
        room_partida="",
        cohorts=("GEI:1r",),
        turn="mati",
        fixed="",
        teachers=_TEACHER,
    )


def _activity(*, activity_id: str, session_id: str, duration_min: int) -> Activity:
    return Activity(
        id=activity_id,
        code="REP",
        kind="TE",
        session_ids=(session_id,),
        students=10,
        turn="mati",
        fixed="",
        teachers=_TEACHER,
        cohorts=("GEI:1r",),
        duration_min=duration_min,
    )


def _pair(activity_id: str, duration_min: int, group: str) -> tuple[Session, Activity]:
    session_id = f"S_{activity_id}"
    return (
        _session(
            sid=session_id,
            activity_id=activity_id,
            duration_min=duration_min,
            group=group,
        ),
        _activity(activity_id=activity_id, session_id=session_id, duration_min=duration_min),
    )


def _neighborhood_fixture() -> _Neighborhood:
    """One unplaced activity, one long clasher, many short distractors (same teacher)."""
    sessions: dict[str, Session] = {}
    activities: dict[str, Activity] = {}
    placed: dict[str, tuple[int, int]] = {}
    activity_day: dict[str, str] = {}
    activity_start: dict[str, int] = {}

    unplaced_session, unplaced_activity = _pair(_UNPLACED_ID, _LONG_DURATION, "TE/11")
    sessions[unplaced_session.id] = unplaced_session
    activities[unplaced_activity.id] = unplaced_activity

    long_session, long_activity = _pair(_LONG_ID, _LONG_DURATION, "TE/21")
    sessions[long_session.id] = long_session
    activities[long_activity.id] = long_activity
    placed[_LONG_ID] = (0, _START)
    activity_day[_LONG_ID] = "L"
    activity_start[_LONG_ID] = _START

    for index in range(_SHORT_COUNT):
        short_id = f"SHORT_{index:03d}"
        short_session, short_activity = _pair(short_id, _SHORT_DURATION, f"TE/{index}1")
        sessions[short_session.id] = short_session
        activities[short_activity.id] = short_activity
        day_idx = index % 5
        placed[short_id] = (day_idx, _START)
        activity_day[short_id] = ("L", "M", "X", "J", "V")[day_idx]
        activity_start[short_id] = _START

    data = TimetableData(sessions=sessions, rooms={}, activities=activities)
    return _Neighborhood(
        data=data,
        placed=placed,
        activity_day=activity_day,
        activity_start=activity_start,
        unplaced=[_UNPLACED_ID],
        long_id=_LONG_ID,
    )


def _two_activity_neighborhood() -> _Neighborhood:
    sessions: dict[str, Session] = {}
    activities: dict[str, Activity] = {}
    unplaced_session, unplaced_activity = _pair(_UNPLACED_ID, 60, "TE/11")
    placed_session, placed_activity = _pair("PLACED", 60, "TE/21")
    sessions[unplaced_session.id] = unplaced_session
    sessions[placed_session.id] = placed_session
    activities[unplaced_activity.id] = unplaced_activity
    activities[placed_activity.id] = placed_activity
    data = TimetableData(sessions=sessions, rooms={}, activities=activities)
    return _Neighborhood(
        data=data,
        placed={"PLACED": (0, _START)},
        activity_day={"PLACED": "L"},
        activity_start={"PLACED": _START},
        unplaced=[_UNPLACED_ID],
        long_id="PLACED",
    )


def _repair_status(result: object) -> object:
    """I-B may return None plus LAST_STATUS, a status-bearing object, or a 4-tuple."""
    status_attr = getattr(result, "status", None)
    if status_attr is not None:
        return status_attr
    if isinstance(result, tuple) and len(result) >= 4:
        return result[3]
    return getattr(repair_mod, "LAST_STATUS", None)


def _is_unknown_status(status: object) -> bool:
    if status == cp_model.UNKNOWN:
        return True
    label = str(status).upper().replace("CPSOLVERSTATUS.", "")
    return label == "UNKNOWN"


def test_repair_unknown_is_not_proven_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _two_activity_neighborhood()

    def _unknown_solve(self: object, model: object, *args: object, **kwargs: object) -> int:
        return int(cp_model.UNKNOWN)

    monkeypatch.setattr(repair_mod.cp_model.CpSolver, "Solve", _unknown_solve)
    result = repair_unplaced_with_cpsat(
        fixture.data,
        placed=dict(fixture.placed),
        activity_day=dict(fixture.activity_day),
        activity_start=dict(fixture.activity_start),
        unplaced=list(fixture.unplaced),
        max_time_s=1,
    )
    status = _repair_status(result)
    assert status is not None
    assert "INFEASIBLE" not in str(status).upper()
    assert _is_unknown_status(status)
    if isinstance(result, tuple) and len(result) == 3:
        raise AssertionError("UNKNOWN must not look like a successful 3-tuple repair")


def test_blocking_neighborhood_includes_long_clasher() -> None:
    fixture = _neighborhood_fixture()
    from horaris_solver.solver.local_cpsat_repair import blocking_neighborhood

    free_ids = blocking_neighborhood(
        fixture.data,
        placed=fixture.placed,
        unplaced=fixture.unplaced,
    )
    assert fixture.long_id in free_ids
    assert _UNPLACED_ID in free_ids


def _model_var_names(model: cp_model.CpModel) -> list[str]:
    proto = model.Proto()
    return [variable.name for variable in proto.variables]


def test_repair_model_frees_long_duration_blocker(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _neighborhood_fixture()
    captured: list[cp_model.CpModel] = []

    def _capture_solve(self: object, model: cp_model.CpModel, *args: object, **kwargs: object) -> int:
        captured.append(model)
        return int(cp_model.UNKNOWN)

    monkeypatch.setattr(repair_mod.cp_model.CpSolver, "Solve", _capture_solve)
    repair_unplaced_with_cpsat(
        fixture.data,
        placed=dict(fixture.placed),
        activity_day=dict(fixture.activity_day),
        activity_start=dict(fixture.activity_start),
        unplaced=list(fixture.unplaced),
        max_time_s=1,
    )
    assert captured, "repair must build a CP-SAT model and call Solve"
    names = _model_var_names(captured[0])
    assert f"d_{fixture.long_id}" in names or f"s_{fixture.long_id}" in names


def _custom_pair(
    aid: str,
    *,
    session_date: date = _MONDAY,
    start: int = 9 * 60,
    fixed: str = "",
    teachers: frozenset[str] = _TEACHER,
    group: str = "TE/11",
) -> tuple[Session, Activity]:
    session = replace(
        _session(sid=f"S_{aid}", activity_id=aid, duration_min=60, group=group),
        session_date=session_date,
        day=("L", "M", "X", "J", "V")[session_date.weekday()],
        start_min=start,
        fixed=fixed,
        teachers=teachers,
    )
    activity = replace(
        _activity(activity_id=aid, session_id=session.id, duration_min=60), fixed=fixed, teachers=teachers
    )
    return session, activity


def _custom_data(
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


def test_repair_places_activity_far_from_every_slot() -> None:
    # Partida 16:00 for a morning activity: every legal start is >= 90 min away (old delta domain was 0..48 min).
    data = _custom_data(_custom_pair("U", start=16 * 60))
    result = repair_unplaced_with_cpsat(
        data, placed={}, activity_day={}, activity_start={}, unplaced=["U"], max_time_s=10.0
    )
    assert result is not None, repair_mod.LAST_STATUS
    new_day, new_start, _moved = result
    assert new_day["U"] == "L"
    assert new_start["U"] in slots_for_duration(60, "mati")


def test_blocking_neighborhood_never_frees_pinned() -> None:
    data = _custom_data(_custom_pair("U"), _custom_pair("P", fixed="R1-FIXADA", group="TE/21"))
    free_ids = blocking_neighborhood(data, placed={"P": (0, 9 * 60)}, unplaced=["U"])
    assert "P" not in free_ids
    assert "U" in free_ids


def test_repair_respects_calendar_and_pinned_neighbour() -> None:
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4))  # Tue..Fri of the partida week
    aturada = CalendarBlock(_MONDAY, 12 * 60, 14 * 60 + 30, "aturada")
    data = _custom_data(
        _custom_pair("U"),
        _custom_pair("P", fixed="R7: PLAB", group="TE/21"),
        calendar=(aturada,),
        days_without_class=closed,
    )
    placed = {"P": (0, 9 * 60)}
    result = repair_unplaced_with_cpsat(
        data,
        placed=placed,
        activity_day={"P": "L"},
        activity_start={"P": 9 * 60},
        unplaced=["U"],
        max_time_s=10.0,
    )
    assert result is not None, repair_mod.LAST_STATUS
    new_day, new_start, _moved = result
    assert (new_day["P"], new_start["P"]) == ("L", 9 * 60)
    assert new_day["U"] == "L"
    assert new_start["U"] in {10 * 60, 10 * 60 + 30, 11 * 60}


def test_repair_empty_domain_is_infeasible() -> None:
    closed = frozenset(date(2026, 9, 15 + i) for i in range(4)) | {date(2026, 9, 21)}
    session_a, activity = _custom_pair("E")
    session_b = replace(session_a, id="S_E2", session_date=date(2026, 9, 22), day="M")
    activity = replace(activity, session_ids=(session_a.id, session_b.id))
    data = TimetableData(
        sessions={session_a.id: session_a, session_b.id: session_b},
        rooms={},
        activities={activity.id: activity},
        days_without_class=closed,
    )
    result = repair_unplaced_with_cpsat(
        data, placed={}, activity_day={}, activity_start={}, unplaced=["E"], max_time_s=5.0
    )
    assert result is None
    assert repair_mod.LAST_STATUS == "INFEASIBLE"


def test_repair_uses_eight_workers_and_optimises(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, bool]] = []

    def _capture_solve(self: cp_model.CpSolver, model: cp_model.CpModel, *args: object, **kwargs: object) -> int:
        seen.append((self.parameters.num_search_workers, self.parameters.stop_after_first_solution))
        return int(cp_model.UNKNOWN)

    monkeypatch.setattr(repair_mod.cp_model.CpSolver, "Solve", _capture_solve)
    fixture = _two_activity_neighborhood()
    repair_unplaced_with_cpsat(
        fixture.data,
        placed=dict(fixture.placed),
        activity_day=dict(fixture.activity_day),
        activity_start=dict(fixture.activity_start),
        unplaced=list(fixture.unplaced),
        max_time_s=1.0,
    )
    assert seen == [(8, False)]


def test_repair_deterministic_uses_one_worker_seed_and_deterministic_time(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, int, float, float]] = []

    def _capture_solve(self: cp_model.CpSolver, model: cp_model.CpModel, *args: object, **kwargs: object) -> int:
        params = self.parameters
        seen.append(
            (params.num_search_workers, params.random_seed, params.max_deterministic_time, params.max_time_in_seconds)
        )
        return int(cp_model.UNKNOWN)

    monkeypatch.setattr(repair_mod.cp_model.CpSolver, "Solve", _capture_solve)
    fixture = _two_activity_neighborhood()
    repair_unplaced_with_cpsat(
        fixture.data,
        placed=dict(fixture.placed),
        activity_day=dict(fixture.activity_day),
        activity_start=dict(fixture.activity_start),
        unplaced=list(fixture.unplaced),
        max_time_s=2.0,
        random_seed=7,
        deterministic=True,
    )
    assert seen == [(1, 7, 2.0, 2.0)]


def test_repair_deterministic_runs_are_identical() -> None:
    data = _custom_data(_custom_pair("U", start=16 * 60), _custom_pair("V", start=16 * 60, group="TE/21"))
    runs = [
        repair_unplaced_with_cpsat(
            data,
            placed={},
            activity_day={},
            activity_start={},
            unplaced=["U", "V"],
            max_time_s=5.0,
            random_seed=3,
            deterministic=True,
        )
        for _ in range(2)
    ]
    assert runs[0] is not None, repair_mod.LAST_STATUS
    assert runs[0] == runs[1]


def test_repair_never_mutates_its_arguments() -> None:
    data = _custom_data(_custom_pair("U", start=16 * 60), _custom_pair("P", fixed="R1-FIXADA", group="TE/21"))
    placed = {"P": (0, 9 * 60)}
    activity_day = {"P": "L"}
    activity_start = {"P": 9 * 60}
    unplaced = ["U"]
    result = repair_unplaced_with_cpsat(
        data,
        placed=placed,
        activity_day=activity_day,
        activity_start=activity_start,
        unplaced=unplaced,
        max_time_s=5.0,
    )
    assert result is not None, repair_mod.LAST_STATUS
    assert placed == {"P": (0, 9 * 60)}
    assert activity_day == {"P": "L"}
    assert activity_start == {"P": 9 * 60}
    assert unplaced == ["U"]
    assert "U" in result[0]


def test_repair_with_nothing_unplaced_returns_new_dicts() -> None:
    activity_day = {"P": "L"}
    activity_start = {"P": 9 * 60}
    result = repair_unplaced_with_cpsat(
        _custom_data(_custom_pair("P")),
        placed={"P": (0, 9 * 60)},
        activity_day=activity_day,
        activity_start=activity_start,
        unplaced=[],
    )
    assert result == ({"P": "L"}, {"P": 9 * 60}, 0)
    assert result[0] is not activity_day
    assert result[1] is not activity_start
