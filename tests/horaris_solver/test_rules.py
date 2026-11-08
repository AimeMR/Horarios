from __future__ import annotations

from datetime import date, timedelta

import pytest

from horaris_solver.domain.models import Activity, Room, Session, TimetableData
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import solve_phase1
from horaris_solver.solver.rules import (
    POOL_EXTENDED,
    POOL_GENERAL,
    SMALL_CLASS_MAX,
    Phase1Rules,
    PoolTable,
    activity_pools,
    fixed_pool_intervals,
    pool_capacity,
    pool_violations,
    sibling_day_conflicts,
    sibling_groups,
    sibling_pairs,
    sibling_violations,
)
from horaris_solver.solver.slots import day_from_index

MONDAY = date(2026, 9, 14)
NEXT_MONDAY = MONDAY + timedelta(days=7)
NINE = 9 * 60


def _session(
    sid: str,
    aid: str,
    *,
    kind: str = "TE",
    code: str = "C1",
    group: str = "G/101",
    session_date: date = MONDAY,
    start: int = NINE,
    duration: int = 60,
    room: str = "",
    fixed: str = "",
    shared_id: str = "",
    sense_espai: bool = False,
) -> Session:
    return Session(
        id=sid,
        activity_id=aid,
        code=code,
        kind=kind,
        group=group,
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida=room,
        cohorts=(f"{code}-1",),
        turn="mati",
        fixed=fixed,
        teachers=frozenset(),
        shared_id=shared_id,
        sense_espai=sense_espai,
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
        sense_espai=first.sense_espai,
    )


def _rooms(general: int = 3, seminars: int = 0, integrated: int = 0, informatica: int = 0) -> dict[str, Room]:
    rooms: dict[str, Room] = {}
    for i in range(general):
        rooms[f"A{i}"] = Room(f"A{i}", "A", "Aules docents", 40)
    for i in range(seminars):
        rooms[f"S{i}"] = Room(f"S{i}", "A", "Seminaris", 20)
    for i in range(integrated):
        rooms[f"L{i}"] = Room(f"L{i}", "A", "Laboratoris docents", 30, "Laboratori integrat")
    for i in range(informatica):
        rooms[f"I{i}"] = Room(f"I{i}", "A", "Aules informàtiques", 30)
    return rooms


def _data(groups: list[list[Session]], rooms: dict[str, Room] | None = None) -> TimetableData:
    sessions = {s.id: s for g in groups for s in g}
    activities = {g[0].activity_id: _activity(g[0].activity_id, g) for g in groups}
    return TimetableData(sessions=sessions, rooms=rooms if rooms is not None else _rooms(), activities=activities)


def test_phase1_rules_defaults_on() -> None:
    rules = Phase1Rules()
    assert rules.same_kind_day and rules.room_pools


@pytest.mark.parametrize(
    ("kind", "sense_espai", "expected"),
    [
        ("TE", False, frozenset({POOL_GENERAL, POOL_EXTENDED})),
        ("SEM", False, frozenset({POOL_GENERAL, POOL_EXTENDED})),
        ("PAUL", False, frozenset({POOL_EXTENDED})),
        ("PLAB", False, frozenset()),
        ("TE", True, frozenset()),
    ],
)
def test_activity_pools_by_kind(kind: str, sense_espai: bool, expected: frozenset[str]) -> None:
    data = _data([[_session("s1", "a1", kind=kind, sense_espai=sense_espai)]])
    assert activity_pools(data, data.activities["a1"]) == expected


def test_pool_capacity_subtracts_reserve_and_excludes_j() -> None:
    rooms = _rooms(general=3, seminars=1, integrated=2, informatica=1)
    rooms["J/1"] = Room("J/1", "J", "Aules docents", 40)
    rooms["J/2"] = Room("J/2", "J", "Aules informàtiques", 40)
    rooms["LAB"] = Room("LAB", "A", "Laboratoris docents", 30, "Lab normal")
    data = _data([[_session("s1", "a1")]], rooms)
    assert pool_capacity(data) == {POOL_GENERAL: 4 - 2, POOL_EXTENDED: 7 - 2}


def test_pool_capacity_never_negative() -> None:
    data = _data([[_session("s1", "a1")]], _rooms(general=1))
    assert pool_capacity(data) == {POOL_GENERAL: 0, POOL_EXTENDED: 0}


def test_te_consumes_general_pool() -> None:
    data = _data([[_session("s1", "a1")], [_session("s2", "a2")]], _rooms(general=3))
    table = PoolTable(data)
    assert table.fits(data.activities["a1"], 0, NINE)
    table.add(data.activities["a1"], 0, NINE)
    assert not table.fits(data.activities["a2"], 0, NINE)
    assert table.fits(data.activities["a2"], 0, NINE + 60)
    assert table.fits(data.activities["a2"], 1, NINE)


def test_paul_only_consumes_extended_pool() -> None:
    rooms = _rooms(general=3, informatica=1)  # G cap 1, GX cap 2
    data = _data([[_session("p1", "pa", kind="PAUL")], [_session("t1", "te")], [_session("t2", "te2")]], rooms)
    table = PoolTable(data)
    table.add(data.activities["pa"], 0, NINE)
    assert table.fits(data.activities["te"], 0, NINE)
    table.add(data.activities["te"], 0, NINE)
    assert not table.fits(data.activities["te2"], 0, NINE)


def test_plab_never_blocked() -> None:
    data = _data([[_session("t1", "te")], [_session("l1", "lab", kind="PLAB")]], _rooms(general=2))
    table = PoolTable(data)
    assert not table.fits(data.activities["te"], 0, NINE)
    assert table.fits(data.activities["lab"], 0, NINE)


def test_fixed_occupancy_reduces_fits() -> None:
    pinned = _session("f1", "fx", room="A0", fixed="R1-FIXADA", start=NINE + 30)
    data = _data([[pinned], [_session("t1", "te")]], _rooms(general=3))
    table = PoolTable(data)
    assert not table.fits(data.activities["te"], 0, NINE)
    assert table.fits(data.activities["te"], 0, NINE - 30)
    assert table.fits(data.activities["te"], 0, NINE + 90)


def test_fixed_occupancy_only_counts_pool_rooms() -> None:
    pinned = _session("f1", "fx", kind="PLAB", room="L0", fixed="R7-PLAB")
    data = _data([[pinned], [_session("p1", "pa", kind="PAUL")], [_session("t1", "te")]], _rooms(3, integrated=1))
    table = PoolTable(data)  # G cap 1 (no fixed); GX cap 2 with 1 fixed (integrated lab)
    table.add(data.activities["te"], 0, NINE)
    assert not table.fits(data.activities["pa"], 0, NINE)


def test_add_remove_symmetric() -> None:
    data = _data([[_session("s1", "a1")], [_session("s2", "a2")]], _rooms(general=3))
    table = PoolTable(data)
    table.add(data.activities["a1"], 2, NINE)
    table.remove(data.activities["a1"], 2, NINE)
    assert table.fits(data.activities["a2"], 2, NINE)
    table.add(data.activities["a2"], 2, NINE)
    assert not table.fits(data.activities["a1"], 2, NINE)


def test_remove_without_add_raises() -> None:
    data = _data([[_session("s1", "a1")]], _rooms(general=3))
    with pytest.raises(ValueError):
        PoolTable(data).remove(data.activities["a1"], 0, NINE)


def test_different_iso_weeks_do_not_interact() -> None:
    data = _data(
        [[_session("s1", "a1")], [_session("s2", "a2", session_date=NEXT_MONDAY)]],
        _rooms(general=3),
    )
    table = PoolTable(data)
    table.add(data.activities["a1"], 0, NINE)
    assert table.fits(data.activities["a2"], 0, NINE)


def test_fixed_pool_intervals_keyed_by_week_and_pool() -> None:
    tuesday = MONDAY + timedelta(days=1)
    pinned = _session("f1", "fx", room="A0", fixed="R1-FIXADA", session_date=tuesday, duration=90)
    mobile = _session("t1", "te", room="A1")
    data = _data([[pinned], [mobile]], _rooms(general=3))
    expected = [(1 * 1440 + NINE, 90, 1)]
    assert fixed_pool_intervals(data) == {(MONDAY, POOL_GENERAL): expected, (MONDAY, POOL_EXTENDED): expected}


def test_pool_violations_reports_overflow() -> None:
    data = _data([[_session("s1", "a1")], [_session("s2", "a2")]], _rooms(general=3))
    violations = pool_violations(data, {"a1": "M", "a2": "M"}, {"a1": NINE, "a2": NINE + 30})
    assert violations
    assert {v.rule for v in violations} == {"D6-POOL"}
    first = violations[0]
    assert first.activity_ids == ("a1", "a2")
    assert "2026-09-15" in first.detail and "09:30" in first.detail
    assert pool_violations(data, {"a1": "M", "a2": "X"}, {"a1": NINE, "a2": NINE}) == []


def test_pool_violations_ignores_pinned_in_mapping() -> None:
    pinned = _session("f1", "fx", room="A0", fixed="R1-FIXADA")
    data = _data([[pinned]], _rooms(general=3))
    assert pool_violations(data, {"fx": "L"}, {"fx": NINE}) == []


def _sibling_data() -> TimetableData:
    return _data(
        [
            [_session("s1", "a1"), _session("s1b", "a1", session_date=NEXT_MONDAY)],
            [_session("s2", "a2", session_date=MONDAY + timedelta(days=2))],
            [_session("s3", "a3", session_date=NEXT_MONDAY)],
            [_session("s4", "a4", group="G/102")],
            [_session("s5", "a5", kind="PAUL")],
        ]
    )


def test_sibling_groups_by_group_code_kind_and_week() -> None:
    groups = {g.key: g.activity_ids for g in sibling_groups(_sibling_data())}
    assert groups == {
        ("G/101", "C1", "TE", MONDAY): ("a1", "a2"),
        ("G/101", "C1", "TE", NEXT_MONDAY): ("a1", "a3"),
    }


def test_sibling_pairs_share_week() -> None:
    assert sibling_pairs(_sibling_data()) == (("a1", "a2"), ("a1", "a3"))


def test_sibling_pairs_exclude_pinned_pinned() -> None:
    data = _data(
        [
            [_session("s1", "a1", fixed="R1-FIXADA")],
            [_session("s2", "a2", fixed="R7-PLAB")],
            [_session("s3", "a3")],
        ]
    )
    assert sibling_pairs(data) == (("a1", "a3"), ("a2", "a3"))


def test_sibling_pairs_exclude_shared_id() -> None:
    data = _data([[_session("s1", "a1", shared_id="X")], [_session("s2", "a2", shared_id="X")]])
    assert sibling_pairs(data) == ()


def test_sibling_day_conflicts_returns_conflicting_sibling() -> None:
    index = {"a1": ("a2", "a3"), "a2": ("a1",), "a3": ("a1",)}
    data = _sibling_data()
    assert sibling_day_conflicts(data, index, "a1", 2, {"a2": "X", "a3": "L"}) == ["a2"]
    assert sibling_day_conflicts(data, index, "a1", 1, {"a2": "X", "a3": "L"}) == []
    assert sibling_day_conflicts(data, index, "a4", 0, {"a2": "L"}) == []


def test_sibling_violations_reported() -> None:
    data = _sibling_data()
    violations = sibling_violations(data, {"a1": "L", "a2": "L", "a3": "M"})
    assert [(v.rule, v.activity_ids) for v in violations] == [("D7-SAME-KIND-DAY", ("a1", "a2"))]
    assert sibling_violations(data, {"a1": "L", "a2": "M", "a3": "X"}) == []


def test_sibling_violations_skip_unassigned() -> None:
    assert sibling_violations(_sibling_data(), {"a1": "L"}) == []


def test_pinned_activity_is_preloaded_not_double_counted() -> None:
    pinned = _session("f1", "fx", room="A0", fixed="R1-FIXADA")
    data = _data([[pinned], [_session("t1", "te")]], _rooms(general=4))
    table = PoolTable(data)
    table.add(data.activities["fx"], 0, NINE)
    assert table.fits(data.activities["te"], 0, NINE)
    assert table.fits(data.activities["fx"], 0, NINE)
    table.remove(data.activities["fx"], 0, NINE)
    assert table.fits(data.activities["te"], 0, NINE)


INFO_CLASS = "C:I0|I1"


def _info_rooms(general: int = 8, informatica: int = 2) -> dict[str, Room]:
    return _rooms(general=general, informatica=informatica)


def _blocked_info_data(*, extra_movable: bool = False) -> TimetableData:
    """Movable PAUL whose only candidates I0/I1 are held at Monday 09:00 by a pinned PAUL and a pinned PLAB."""
    groups = [
        [_session("f1", "pin_paul", kind="PAUL", code="P1", room="I0", fixed="R1-FIXADA")],
        [_session("f2", "pin_plab", kind="PLAB", code="P2", room="I1", fixed="R7-PLAB")],
        [_session("m1", "mov", kind="PAUL", code="P3", room="I0")],
    ]
    if extra_movable:
        groups.append([_session("m2", "mov2", kind="PAUL", code="P4", room="I1", start=NINE + 120)])
    return _data(groups, _info_rooms())


def test_small_candidate_set_adds_class_pool() -> None:
    data = _blocked_info_data()
    assert activity_pools(data, data.activities["mov"]) == frozenset({POOL_EXTENDED, INFO_CLASS})
    assert pool_capacity(data)[INFO_CLASS] == 2


def test_pinned_activity_has_no_class_pool() -> None:
    data = _blocked_info_data()
    assert activity_pools(data, data.activities["pin_paul"]) == frozenset({POOL_EXTENDED})


def test_class_pool_fixed_intervals_count_pinned_sessions_in_its_rooms() -> None:
    data = _blocked_info_data()
    assert fixed_pool_intervals(data)[(MONDAY, INFO_CLASS)] == [(NINE, 60, 1), (NINE, 60, 1)]


def test_greedy_table_rejects_slot_where_all_candidates_are_pinned() -> None:
    data = _blocked_info_data()
    table = PoolTable(data)
    assert not table.fits(data.activities["mov"], 0, NINE)
    assert table.fits(data.activities["mov"], 0, NINE + 60)


def test_class_capacity_counts_movable_demand() -> None:
    data = _blocked_info_data(extra_movable=True)
    table = PoolTable(data)
    table.add(data.activities["mov"], 0, NINE + 120)
    assert table.fits(data.activities["mov2"], 0, NINE + 120)
    table.add(data.activities["mov2"], 0, NINE + 120)
    assert not table.fits(data.activities["mov"], 0, NINE + 120)
    assert pool_violations(data, {"mov": "L", "mov2": "L"}, {"mov": NINE + 120, "mov2": NINE + 120}) == []
    violations = pool_violations(data, {"mov": "L", "mov2": "L"}, {"mov": NINE, "mov2": NINE})
    assert any(INFO_CLASS in v.detail for v in violations)


def test_large_candidate_set_has_no_class_pool() -> None:
    data = _data(
        [[_session("m1", "mov", kind="PAUL", room="I0")]],
        _info_rooms(informatica=SMALL_CLASS_MAX + 1),
    )
    assert activity_pools(data, data.activities["mov"]) == frozenset({POOL_EXTENDED})
    assert not any(pool.startswith("C:") for pool in pool_capacity(data))


def test_candidate_set_covering_a_base_pool_adds_no_class_pool() -> None:
    data = _data([[_session("t1", "te")]], _rooms(general=3))
    assert activity_pools(data, data.activities["te"]) == frozenset({POOL_GENERAL, POOL_EXTENDED})


def test_class_pools_do_not_leak_between_data_objects() -> None:
    blocked = _blocked_info_data()
    assert INFO_CLASS in pool_capacity(blocked)
    big = _data([[_session("m1", "mov", kind="PAUL", room="I0")]], _info_rooms(informatica=SMALL_CLASS_MAX + 1))
    assert activity_pools(big, big.activities["mov"]) == frozenset({POOL_EXTENDED})


def test_cpsat_with_rules_moves_paul_away_from_blocked_candidates() -> None:
    data = _blocked_info_data()
    result = solve_phase1(data, max_time_s=10, num_workers=1, rules=Phase1Rules())
    assert result.ok, result.message
    assert (result.activity_day["mov"], result.activity_start["mov"]) != ("L", NINE)
    assert pool_violations(data, result.activity_day, result.activity_start) == []


def test_greedy_with_rules_moves_paul_away_from_blocked_candidates() -> None:
    data = _blocked_info_data()
    result = solve_phase1_greedy(data, rules=Phase1Rules())
    assert result.ok, result.message
    assert (result.activity_day["mov"], result.activity_start["mov"]) != ("L", NINE)


def test_fixed_sessions_sharing_a_class_room_take_it_once() -> None:
    groups = [
        [_session("f1", "pin_a", kind="PAUL", code="P1", room="I0", fixed="R1-FIXADA")],
        [_session("f2", "pin_b", kind="PAUL", code="P2", room="I0", fixed="R1-FIXADA", start=NINE + 30)],
        [_session("m1", "mov", kind="PAUL", code="P3", room="I0")],
    ]
    data = _data(groups, _info_rooms())
    assert fixed_pool_intervals(data)[(MONDAY, INFO_CLASS)] == [(NINE, 90, 1)]
    table = PoolTable(data)
    assert table.fits(data.activities["mov"], 0, NINE)
