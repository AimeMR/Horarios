from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, CalendarBlock, Room, Session, TimetableData
from horaris_solver.solver.precheck import PrecheckIssue, PrecheckReport, _peak, run_precheck
from horaris_solver.solver.rules import Phase1Rules
from horaris_solver.solver.slots import day_from_index

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)
NINE = 9 * 60
RULES = Phase1Rules()


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
    turn: str = "mati",
    teachers: frozenset[str] = frozenset(),
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
        turn=turn,
        fixed=fixed,
        teachers=teachers,
        shared_id=shared_id,
    )


def _activity(aid: str, sessions: list[Session]) -> Activity:
    first = sessions[0]
    return Activity(
        id=aid,
        code=first.code,
        kind=first.kind,
        session_ids=tuple(s.id for s in sessions),
        students=10,
        turn=first.turn,
        fixed=first.fixed,
        teachers=frozenset().union(*(s.teachers for s in sessions)),
        cohorts=first.cohorts,
        duration_min=first.duration_min,
    )


def _data(
    groups: list[list[Session]],
    *,
    rooms: dict[str, Room] | None = None,
    calendar: tuple[CalendarBlock, ...] = (),
    days_without_class: frozenset[date] = frozenset(),
) -> TimetableData:
    sessions = {s.id: s for g in groups for s in g}
    activities = {g[0].activity_id: _activity(g[0].activity_id, g) for g in groups}
    return TimetableData(
        sessions=sessions,
        rooms=rooms or {},
        activities=activities,
        calendar=calendar,
        days_without_class=days_without_class,
    )


def _codes(report: PrecheckReport) -> set[str]:
    return {issue.code for issue in report.issues}


def _only(report: PrecheckReport, code: str) -> PrecheckIssue:
    matches = [issue for issue in report.issues if issue.code == code]
    assert len(matches) == 1, report.issues
    return matches[0]


def test_clean_data_has_no_issues() -> None:
    data = _data([[_session("s1", "a1")], [_session("s2", "a2", code="C2")]])
    report = run_precheck(data, RULES)
    assert report.issues == ()
    assert not report.blocking


def test_mini_paquet_has_no_blocking_issues() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    report = run_precheck(data, RULES)
    assert not report.blocking, report.issues


def test_empty_domain_is_blocking() -> None:
    tuesday = MONDAY + timedelta(days=1)
    # The partida weekday always stays legal; days_without_class closes the rest and an aturada closes the turn.
    data = _data(
        [[_session("s1", "a1", session_date=tuesday, turn="tarda", start=NINE)]],
        calendar=(CalendarBlock(tuesday, 14 * 60, 22 * 60, "aturada"),),
        days_without_class=frozenset(MONDAY + timedelta(days=d) for d in range(5)) - {tuesday},
    )
    issue = _only(run_precheck(data), "EMPTY_DOMAIN")
    assert issue.blocking
    assert issue.activity_ids == ("a1",)


def test_empty_domain_from_aturades() -> None:
    monday = CalendarBlock(MONDAY, 14 * 60, 22 * 60, "aturada")
    rest = tuple(CalendarBlock(MONDAY + timedelta(days=d), 8 * 60, 22 * 60, "aturada") for d in range(1, 5))
    data = _data([[_session("s1", "a1", turn="tarda", start=NINE)]], calendar=(monday, *rest))
    issue = _only(run_precheck(data), "EMPTY_DOMAIN")
    assert issue.blocking


def test_empty_domain_from_turn_too_long() -> None:
    data = _data([[_session("s1", "a1", duration=7 * 60)]])
    issue = _only(run_precheck(data), "EMPTY_DOMAIN")
    assert issue.blocking


def test_shared_group_without_common_slot_is_blocking() -> None:
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", turn="mati")],
            [_session("s2", "a2", shared_id="X", turn="tarda", start=15 * 60, code="C2")],
        ]
    )
    issue = _only(run_precheck(data), "SHARED_NO_COMMON_SLOT")
    assert issue.blocking
    assert issue.activity_ids == ("a1", "a2")


def test_shared_group_pinned_member_uses_partida_value() -> None:
    pinned = _session("s1", "a1", shared_id="X", fixed="R1-FIXADA", start=NINE)
    tuesday = MONDAY + timedelta(days=1)
    week = frozenset(MONDAY + timedelta(days=d) for d in range(5)) - {tuesday}
    movable = _session("s2", "a2", shared_id="X", code="C2", session_date=tuesday)
    data = _data([[pinned], [movable]], days_without_class=week)
    issue = _only(run_precheck(data), "SHARED_NO_COMMON_SLOT")
    assert issue.blocking


def test_shared_group_with_common_slot_is_clean() -> None:
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", fixed="R1-FIXADA")],
            [_session("s2", "a2", shared_id="X", code="C2")],
        ]
    )
    assert "SHARED_NO_COMMON_SLOT" not in _codes(run_precheck(data))


def test_shared_group_two_pinned_at_different_slots_is_not_blocking() -> None:
    # CP-SAT never links two pinned members, so their differing partida slots are inherited, not infeasible.
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", fixed="R1-FIXADA", start=NINE)],
            [_session("s2", "a2", shared_id="X", fixed="R1-FIXADA", code="C2", start=NINE + 120)],
        ]
    )
    report = run_precheck(data)
    assert "SHARED_NO_COMMON_SLOT" not in _codes(report)
    assert not report.blocking


def test_shared_group_movable_is_checked_only_against_pinned_root() -> None:
    # a1 (root) and a3 are pinned at different slots; a2 can reach a1's slot, so shared_links links it to a1 only.
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", fixed="R1-FIXADA", start=NINE)],
            [_session("s2", "a2", shared_id="X", code="C2")],
            [_session("s3", "a3", shared_id="X", fixed="R1-FIXADA", code="C3", start=NINE + 120)],
        ]
    )
    assert "SHARED_NO_COMMON_SLOT" not in _codes(run_precheck(data))


def test_shared_group_movable_unreachable_from_pinned_root_is_blocking() -> None:
    tuesday = MONDAY + timedelta(days=1)
    week = frozenset(MONDAY + timedelta(days=d) for d in range(5)) - {tuesday}
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", fixed="R1-FIXADA", start=NINE)],
            [_session("s2", "a2", shared_id="X", code="C2", session_date=tuesday)],
            [_session("s3", "a3", shared_id="X", fixed="R1-FIXADA", code="C3", start=NINE + 120)],
        ],
        days_without_class=week,
    )
    issue = _only(run_precheck(data), "SHARED_NO_COMMON_SLOT")
    assert issue.blocking
    assert issue.activity_ids == ("a1", "a2")


def test_shared_group_pinned_out_of_turn_root_uses_partida_slot() -> None:
    # The pinned root sits outside its turn (no legal domain) but CP-SAT still pins it at partida.
    data = _data(
        [
            [_session("s1", "a1", shared_id="X", fixed="R1-FIXADA", turn="tarda", start=NINE)],
            [_session("s2", "a2", shared_id="X", code="C2", turn="tarda", start=15 * 60)],
        ]
    )
    issue = _only(run_precheck(data), "SHARED_NO_COMMON_SLOT")
    assert issue.activity_ids == ("a1", "a2")


def test_heterogeneous_activity_is_blocking() -> None:
    data = _data([[_session("s1", "a1"), _session("s2", "a1", start=NINE + 60, session_date=MONDAY + timedelta(7))]])
    issue = _only(run_precheck(data), "HETEROGENEOUS_ACTIVITY")
    assert issue.blocking
    assert issue.activity_ids == ("a1",)


def test_homogeneous_multi_week_activity_is_clean() -> None:
    data = _data([[_session("s1", "a1"), _session("s2", "a1", session_date=MONDAY + timedelta(7))]])
    assert run_precheck(data).issues == ()


def test_pinned_out_of_turn_is_warning() -> None:
    data = _data([[_session("s1", "a1", fixed="R1-FIXADA", turn="tarda", start=NINE)]])
    issue = _only(run_precheck(data), "PINNED_OUT_OF_TURN")
    assert not issue.blocking
    assert issue.activity_ids == ("a1",)
    assert not run_precheck(data).blocking


def test_pinned_clash_is_warning() -> None:
    teacher = frozenset({"T"})
    data = _data(
        [
            [_session("s1", "a1", fixed="R1-FIXADA", teachers=teacher)],
            [_session("s2", "a2", fixed="R7-PLAB", code="C2", start=NINE + 30, teachers=teacher)],
            [_session("s3", "a3", fixed="R1-FIXADA", code="C3", start=NINE + 60, teachers=teacher)],
        ]
    )
    report = run_precheck(data)
    clashes = [issue for issue in report.issues if issue.code == "PINNED_CLASH"]
    assert [c.activity_ids for c in clashes] == [("a1", "a2"), ("a2", "a3")]
    assert not any(c.blocking for c in clashes)
    assert not report.blocking


def test_pinned_non_interacting_overlap_is_clean() -> None:
    data = _data(
        [
            [_session("s1", "a1", fixed="R1-FIXADA", teachers=frozenset({"T1"}))],
            [_session("s2", "a2", fixed="R1-FIXADA", code="C2", teachers=frozenset({"T2"}))],
        ]
    )
    assert "PINNED_CLASH" not in _codes(run_precheck(data))


def _siblings(count: int, forbidden_days: int) -> TimetableData:
    days = frozenset(MONDAY + timedelta(days=d) for d in range(5 - forbidden_days, 5))
    groups = [[_session(f"s{i}", f"a{i}")] for i in range(count)]
    return _data(groups, days_without_class=days)


def test_siblings_exceed_days_is_blocking() -> None:
    issue = _only(run_precheck(_siblings(4, 2), RULES), "SIBLINGS_EXCEED_DAYS")
    assert issue.blocking
    assert issue.activity_ids == ("a0", "a1", "a2", "a3")


def test_siblings_within_days_is_clean() -> None:
    assert "SIBLINGS_EXCEED_DAYS" not in _codes(run_precheck(_siblings(3, 2), RULES))


def test_siblings_pinned_days_are_taken() -> None:
    pinned = [_session(f"p{d}", f"p{d}", fixed="R1-FIXADA", session_date=MONDAY + timedelta(days=d)) for d in range(4)]
    movable = [_session("m1", "m1"), _session("m2", "m2")]
    data = _data([[s] for s in pinned + movable])
    issue = _only(run_precheck(data, RULES), "SIBLINGS_EXCEED_DAYS")
    assert issue.activity_ids == ("m1", "m2")


def test_siblings_shared_count_once() -> None:
    groups = [[_session(f"s{i}", f"a{i}", shared_id="X")] for i in range(4)]
    days = frozenset(MONDAY + timedelta(days=d) for d in range(1, 5))
    data = _data(groups, days_without_class=days)
    assert "SIBLINGS_EXCEED_DAYS" not in _codes(run_precheck(data, RULES))


def test_siblings_check_respects_rule_flag() -> None:
    rules = Phase1Rules(same_kind_day=False, room_pools=True)
    assert "SIBLINGS_EXCEED_DAYS" not in _codes(run_precheck(_siblings(4, 2), rules))


def _pool_rooms(count: int) -> dict[str, Room]:
    return {f"A{i}": Room(f"A{i}", "A", "Aules docents", 40) for i in range(count)}


def _pool_data(fixed_count: int) -> TimetableData:
    groups = [
        [_session(f"f{i}", f"f{i}", code=f"C{i}", fixed="R1-FIXADA", room=f"A{i}", start=NINE + 20 * i)]
        for i in range(fixed_count)
    ]
    return _data(groups, rooms=_pool_rooms(4))  # capacity 4 - 2 = 2; all sessions overlap 09:40-10:00


def test_pool_over_capacity_is_warning() -> None:
    report = run_precheck(_pool_data(3), RULES)
    issues = [issue for issue in report.issues if issue.code == "POOL_OVER_CAPACITY"]
    assert issues
    assert not any(issue.blocking for issue in issues)
    assert not report.blocking


def test_pool_within_capacity_is_clean() -> None:
    assert "POOL_OVER_CAPACITY" not in _codes(run_precheck(_pool_data(2), RULES))


def test_pool_back_to_back_fixed_sessions_do_not_overlap() -> None:
    # 09:00-10:00, 10:00-11:00, 11:00-12:00: peak 1 under capacity 2 even though 3 sessions exceed it.
    groups = [
        [_session(f"f{i}", f"f{i}", code=f"C{i}", fixed="R1-FIXADA", room=f"A{i}", start=NINE + 60 * i)]
        for i in range(3)
    ]
    data = _data(groups, rooms=_pool_rooms(4))
    assert "POOL_OVER_CAPACITY" not in _codes(run_precheck(data, RULES))


def test_peak_counts_back_to_back_as_one() -> None:
    assert _peak([(0, 60, 1), (60, 60, 1), (120, 60, 1)]) == 1
    assert _peak([(0, 60, 1), (59, 60, 2)]) == 3


def test_pool_check_respects_rule_flag() -> None:
    rules = Phase1Rules(same_kind_day=True, room_pools=False)
    assert "POOL_OVER_CAPACITY" not in _codes(run_precheck(_pool_data(3), rules))


def test_rules_none_skips_rule_checks() -> None:
    assert "SIBLINGS_EXCEED_DAYS" not in _codes(run_precheck(_siblings(4, 2)))
    assert "POOL_OVER_CAPACITY" not in _codes(run_precheck(_pool_data(3)))


def test_messages_do_not_leak_teacher_names() -> None:
    teacher = frozenset({"Secret Name"})
    data = _data(
        [
            [_session("s1", "a1", fixed="R1-FIXADA", teachers=teacher)],
            [_session("s2", "a2", fixed="R1-FIXADA", code="C2", teachers=teacher)],
        ]
    )
    report = run_precheck(data)
    assert report.issues
    assert all("Secret" not in issue.message for issue in report.issues)


def _closed_days(days: range) -> tuple[CalendarBlock, ...]:
    """Whole-day aturades (one-off closures) on the given weekday offsets of the test week."""
    return tuple(CalendarBlock(MONDAY + timedelta(days=d), 8 * 60, 22 * 60, "aturada") for d in days)


def _overload_data(
    *,
    starts: tuple[int, int, int] = (15 * 60, 17 * 60, 19 * 60),
    teachers: tuple[str, str, str] = ("Secret Name", "Secret Name", "Secret Name"),
    closed: range = range(1, 5),
) -> TimetableData:
    durations = (120, 120, 180)
    groups = [
        [
            _session(
                f"s{i}",
                f"a{i}",
                code=f"C{i}",
                turn="tarda",
                start=starts[i],
                duration=durations[i],
                teachers=frozenset({teachers[i]}),
            )
        ]
        for i in range(3)
    ]
    return _data(groups, calendar=_closed_days(closed))


def test_single_day_overload_is_blocking() -> None:
    issue = _only(run_precheck(_overload_data()), "SINGLE_DAY_OVERLOAD")
    assert issue.blocking
    assert issue.activity_ids == ("a0", "a1", "a2")
    assert "420" in issue.message and "390" in issue.message
    assert MONDAY.isoformat() in issue.message
    assert "weekday L" in issue.message
    assert "single legal weekday due to calendar closures" in issue.message
    assert "Secret" not in issue.message
    assert "C0" not in issue.message


def test_single_day_overload_with_inherited_pair_is_clean() -> None:
    # a0/a1 already overlap in partida: the solver only penalises that pair, so it is not forced apart.
    data = _overload_data(starts=(15 * 60, 16 * 60, 18 * 60))
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def _single_day(sessions: list[Session]) -> TimetableData:
    return _data([[s] for s in sessions], calendar=_closed_days(range(1, 5)))


def _tarda(sid: str, start: int, duration: int, *, fixed: str = "") -> Session:
    return _session(
        sid, sid, code=sid, turn="tarda", start=start, duration=duration, fixed=fixed, teachers=frozenset({"T"})
    )


def test_single_day_overload_pinned_clash_does_not_block() -> None:
    # Two pinned clash with each other (exempt); the movable only has to avoid their union (15:00-18:00).
    data = _single_day(
        [
            _tarda("p1", 15 * 60, 120, fixed="R1-FIXADA"),
            _tarda("p2", 16 * 60, 120, fixed="R1-FIXADA"),
            _tarda("m1", 18 * 60, 180),
        ]
    )
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def test_single_day_overload_pinned_outside_window_does_not_block() -> None:
    # The pinned session sits outside the tarda window, so it does not consume window minutes.
    data = _single_day(
        [
            _tarda("p1", 9 * 60, 120, fixed="R1-FIXADA"),
            _tarda("m1", 15 * 60, 180),
            _tarda("m2", 18 * 60, 120),
        ]
    )
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def test_single_day_overload_counts_pinned_inside_window() -> None:
    # Pinned 14:30-16:30 leaves 270 free minutes; the movables need 300 and must avoid it and each other.
    data = _single_day(
        [
            _tarda("p1", 14 * 60 + 30, 120, fixed="R1-FIXADA"),
            _tarda("m1", 16 * 60 + 30, 180),
            _tarda("m2", 21 * 60, 120),
        ]
    )
    issue = _only(run_precheck(data), "SINGLE_DAY_OVERLOAD")
    assert issue.blocking
    assert issue.activity_ids == ("m1", "m2", "p1")
    assert "300" in issue.message and "270" in issue.message


def test_single_day_overload_unknown_turn_uses_both_windows() -> None:
    sessions = [
        _session(
            f"s{i}", f"a{i}", code=f"C{i}", turn="?", start=NINE + 150 * i, duration=140, teachers=frozenset({"T"})
        )
        for i in range(3)
    ]
    data = _single_day(sessions)
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def test_single_day_non_interacting_is_clean() -> None:
    data = _overload_data(teachers=("T0", "T1", "T2"))
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def test_single_day_overload_ignores_two_allowed_days() -> None:
    data = _overload_data(closed=range(2, 5))
    assert "SINGLE_DAY_OVERLOAD" not in _codes(run_precheck(data))


def test_single_day_overload_from_days_without_class() -> None:
    # Back-to-back partida starts (no inherited overlap), so all three must be forced apart.
    groups = [
        [_session(f"s{i}", f"a{i}", code=f"C{i}", start=NINE + 150 * i, duration=150, teachers=frozenset({"T"}))]
        for i in range(3)
    ]
    week = frozenset(MONDAY + timedelta(days=d) for d in range(1, 5))
    issue = _only(run_precheck(_data(groups, days_without_class=week)), "SINGLE_DAY_OVERLOAD")
    assert "450" in issue.message and "360" in issue.message


def test_report_blocking_property() -> None:
    warn = PrecheckIssue("W", ("a",), "w", blocking=False)
    block = PrecheckIssue("B", ("a",), "b", blocking=True)
    assert not PrecheckReport((warn,)).blocking
    assert PrecheckReport((warn, block)).blocking
    assert not PrecheckReport(()).blocking
