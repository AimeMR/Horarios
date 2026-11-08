from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, Room, Session, TimetableData
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import Phase1Result, solve_phase1
from horaris_solver.solver.rules import Phase1Rules, PoolTable, pool_violations, sibling_violations
from horaris_solver.solver.slots import day_from_index
from horaris_solver.solver.validate import validate_phase1

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)
NEXT_MONDAY = MONDAY + timedelta(days=7)
NINE = 9 * 60
ELEVEN = 11 * 60

SIBLINGS_ONLY = Phase1Rules(same_kind_day=True, room_pools=False)
POOLS_ONLY = Phase1Rules(same_kind_day=False, room_pools=True)


def _session(
    sid: str,
    aid: str,
    *,
    code: str,
    group: str,
    session_date: date = MONDAY,
    start: int = NINE,
    room: str = "",
    fixed: str = "",
) -> Session:
    return Session(
        id=sid,
        activity_id=aid,
        code=code,
        kind="TE",
        group=group,
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=60,
        students=10,
        room_partida=room,
        cohorts=(f"COH_{aid}",),
        turn="mati",
        fixed=fixed,
        teachers=frozenset(),
    )


def _activity(aid: str, sessions: list[Session]) -> Activity:
    first = sessions[0]
    return Activity(
        id=aid,
        code=first.code,
        kind=first.kind,
        session_ids=tuple(s.id for s in sessions),
        students=10,
        turn="mati",
        fixed=first.fixed,
        teachers=frozenset(),
        cohorts=first.cohorts,
        duration_min=first.duration_min,
    )


def _rooms(general: int) -> dict[str, Room]:
    return {f"A{i}": Room(f"A{i}", "A", "Aules docents", 40) for i in range(general)}


def _data(groups: list[list[Session]], rooms: dict[str, Room] | None = None) -> TimetableData:
    return TimetableData(
        sessions={s.id: s for g in groups for s in g},
        rooms=rooms if rooms is not None else _rooms(6),
        activities={g[0].activity_id: _activity(g[0].activity_id, g) for g in groups},
    )


def _assert_rules_hold(data: TimetableData, result: Phase1Result) -> None:
    assert result.ok, result.message
    assert sibling_violations(data, result.activity_day) == []
    assert pool_violations(data, result.activity_day, result.activity_start) == []


def _sibling_data() -> TimetableData:
    return _data(
        [
            [_session("s1", "a1", code="C1", group="G/1")],
            [_session("s2", "a2", code="C1", group="G/1", start=ELEVEN)],
        ]
    )


def test_without_rules_siblings_stay_on_same_day() -> None:
    result = solve_phase1(_sibling_data(), max_time_s=10, num_workers=1)
    assert result.ok, result.message
    assert result.activity_day == {"a1": "L", "a2": "L"}
    assert result.objective == 0


def test_rules_put_same_kind_siblings_on_different_days() -> None:
    data = _sibling_data()
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=SIBLINGS_ONLY)
    _assert_rules_hold(data, result)
    assert result.activity_day["a1"] != result.activity_day["a2"]


def test_rules_ignore_siblings_in_different_iso_weeks() -> None:
    data = _data(
        [
            [_session("s1", "a1", code="C1", group="G/1")],
            [_session("s2", "a2", code="C1", group="G/1", session_date=NEXT_MONDAY)],
        ]
    )
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=SIBLINGS_ONLY)
    assert result.ok, result.message
    assert result.activity_day == {"a1": "L", "a2": "L"}


def test_pinned_sibling_forces_movable_off_its_day() -> None:
    data = _data(
        [
            [_session("p1", "pin", code="C1", group="G/1", fixed="R1-FIXADA")],
            [_session("m1", "mov", code="C1", group="G/1", start=ELEVEN)],
        ]
    )
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=SIBLINGS_ONLY)
    _assert_rules_hold(data, result)
    assert result.activity_day["pin"] == "L"
    assert result.activity_start["pin"] == NINE
    assert result.activity_day["mov"] != "L"


def test_day_change_cost_scales_with_sessions_when_rules_given() -> None:
    movable = [
        _session("m1", "mov", code="C1", group="G/1", start=ELEVEN),
        _session("m2", "mov", code="C1", group="G/1", start=ELEVEN, session_date=NEXT_MONDAY),
    ]
    data = _data([[_session("p1", "pin", code="C1", group="G/1", fixed="R1-FIXADA")], movable])
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=SIBLINGS_ONLY)
    assert result.ok, result.message
    assert result.activity_start["mov"] == ELEVEN
    assert result.objective == 2 * 200


def _pool_pair(rooms: int) -> TimetableData:
    return _data(
        [
            [_session("s1", "a1", code="C1", group="G/1")],
            [_session("s2", "a2", code="C2", group="G/2")],
        ],
        _rooms(rooms),
    )


def test_without_rules_independent_activities_may_overlap() -> None:
    result = solve_phase1(_pool_pair(3), max_time_s=10, num_workers=1)
    assert result.ok, result.message
    assert result.activity_day == {"a1": "L", "a2": "L"}
    assert result.activity_start == {"a1": NINE, "a2": NINE}


def test_pool_capacity_one_forces_overlapping_activities_apart() -> None:
    data = _pool_pair(3)  # 3 rooms - reserve 2 = capacity 1
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=POOLS_ONLY)
    _assert_rules_hold(data, result)
    same_slot = (
        result.activity_day["a1"] == result.activity_day["a2"]
        and result.activity_start["a1"] == result.activity_start["a2"]
    )
    assert not same_slot


def test_pool_capacity_two_allows_overlap() -> None:
    data = _pool_pair(4)
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=POOLS_ONLY)
    _assert_rules_hold(data, result)
    assert result.objective == 0


def test_fixed_occupancy_consumes_pool_capacity() -> None:
    data = _data(
        [
            [_session("p1", "pin", code="C1", group="G/1", room="A0", fixed="R1-FIXADA")],
            [_session("m1", "mov", code="C2", group="G/2")],
        ],
        _rooms(3),
    )
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=POOLS_ONLY)
    _assert_rules_hold(data, result)
    assert (result.activity_day["mov"], result.activity_start["mov"]) != ("L", NINE)


def test_fixed_overlap_above_capacity_relaxes_and_reports() -> None:
    data = _data(
        [
            [_session("p1", "pin1", code="C1", group="G/1", room="A0", fixed="R1-FIXADA")],
            [_session("p2", "pin2", code="C2", group="G/2", room="A1", fixed="R1-FIXADA")],
            [_session("m1", "mov", code="C3", group="G/3", start=ELEVEN)],
            [_session("m2", "mov2", code="C4", group="G/4", start=ELEVEN)],
        ],
        _rooms(3),
    )
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=POOLS_ONLY)
    assert result.ok, result.message
    assert "D6" in result.message
    assert "exceeds" in result.message
    # Capacity stays 1 away from the pinned overflow: only one movable keeps 11:00, the other moves.
    slots = {(result.activity_day[a], result.activity_start[a]) for a in ("mov", "mov2")}
    assert len(slots) == 2
    assert ("L", ELEVEN) in slots
    assert ("L", NINE) not in slots
    assert pool_violations(data, result.activity_day, result.activity_start) == []
    assert validate_phase1(data, result, POOLS_ONLY) == []


def test_pinned_overflow_does_not_raise_capacity_elsewhere() -> None:
    data = _data(
        [
            [_session("p1", "pin1", code="C1", group="G/1", room="A0", fixed="R1-FIXADA")],
            [_session("p2", "pin2", code="C2", group="G/2", room="A1", fixed="R1-FIXADA")],
            [_session("m1", "mov", code="C3", group="G/3", start=ELEVEN)],
            [_session("m2", "mov2", code="C4", group="G/4", start=ELEVEN)],
        ],
        _rooms(3),
    )
    both_at_eleven = {"pin1": "L", "pin2": "L", "mov": "L", "mov2": "L"}
    starts = {"pin1": NINE, "pin2": NINE, "mov": ELEVEN, "mov2": ELEVEN}
    violations = pool_violations(data, both_at_eleven, starts)
    assert violations  # pools G and GX, two 30-minute slots each
    assert {(v.rule, v.activity_ids) for v in violations} == {("D6-POOL", ("mov", "mov2"))}
    table = PoolTable(data)
    assert table.fits(data.activities["mov"], 0, ELEVEN)
    table.add(data.activities["mov"], 0, ELEVEN)
    assert not table.fits(data.activities["mov2"], 0, ELEVEN)
    assert not table.fits(data.activities["mov2"], 0, NINE)


def _slack_data() -> TimetableData:
    """Pinned sessions (one pool overflow at 9:00), same-kind siblings and movables with room to spare."""
    pinned = [
        [_session(f"p{i}", f"pin{i}", code=f"P{i}", group=f"P/{i}", room=f"A{i}", fixed="R1-FIXADA")] for i in range(3)
    ]
    siblings = [[_session(f"s{i}", f"sib{i}", code="SIB", group="S/1", start=NINE + 60 * i)] for i in range(3)]
    movable = [[_session(f"m{i}", f"mov{i}", code=f"M{i}", group=f"M/{i}", start=ELEVEN)] for i in range(4)]
    return _data(pinned + siblings + movable, _rooms(4))


@pytest.mark.parametrize("seed", [None, 0, 1, 2, 3, 4])
def test_greedy_candidates_pass_rules_and_cpsat_accepts_them_as_hint(seed: int | None) -> None:
    data = _slack_data()
    rules = Phase1Rules()
    candidate = solve_phase1_greedy(data, seed=seed, rules=rules, repair_time_s=5)
    assert candidate.ok, candidate.message
    assert pool_violations(data, candidate.activity_day, candidate.activity_start) == []
    assert sibling_violations(data, candidate.activity_day) == []
    assert validate_phase1(data, candidate, rules) == []
    hinted = solve_phase1(data, max_time_s=10, hints=candidate, rules=rules, random_seed=0, deterministic=True)
    assert hinted.status in ("OPTIMAL", "FEASIBLE"), hinted.message
    assert validate_phase1(data, hinted, rules) == []


def test_rules_none_reproduces_previous_mini_paquet_result() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    explicit = solve_phase1(data, max_time_s=30, random_seed=0, num_workers=1, rules=None)
    assert explicit.status == "OPTIMAL"
    assert explicit.objective == 0
    assert explicit.activity_day == {"A1": "L", "A2": "M", "A3": "L", "A4": "M"}
    assert explicit.activity_start == {"A1": 510, "A2": 630, "A3": 900, "A4": 510}


def test_mini_paquet_with_rules_respects_d6_d7() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30, num_workers=1, rules=Phase1Rules())
    _assert_rules_hold(data, result)


def test_deterministic_runs_are_identical() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    runs = [solve_phase1(data, max_time_s=5, random_seed=3, rules=Phase1Rules(), deterministic=True) for _ in range(2)]
    assert runs[0].ok, runs[0].message
    assert runs[0] == runs[1]


def test_deterministic_pool_instance_is_repeatable() -> None:
    data = _pool_pair(3)
    first = solve_phase1(data, max_time_s=5, rules=Phase1Rules(), deterministic=True)
    second = solve_phase1(data, max_time_s=5, rules=Phase1Rules(), deterministic=True)
    _assert_rules_hold(data, first)
    assert first == second
