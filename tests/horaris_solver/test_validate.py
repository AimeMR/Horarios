from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, Room, Session, TimetableData
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import Phase1Result, solve_phase1
from horaris_solver.solver.rules import Phase1Rules
from horaris_solver.solver.slots import day_from_index
from horaris_solver.solver.validate import validate_phase1
from horaris_solver.solver.violations import Violation

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)
NEXT_MONDAY = MONDAY + timedelta(days=7)
NINE = 9 * 60
TEN = 10 * 60
FOUR_PM = 16 * 60


def _pair(
    aid: str,
    *,
    session_date: date = MONDAY,
    start: int = NINE,
    duration: int = 60,
    turn: str = "mati",
    fixed: str = "",
    teachers: frozenset[str] = frozenset(),
    shared_id: str = "",
    code: str | None = None,
    group: str | None = None,
) -> tuple[Session, Activity]:
    code = code or f"C-{aid}"
    session = Session(
        id=f"S-{aid}",
        activity_id=aid,
        code=code,
        kind="TE",
        group=group or f"G/{aid}",
        session_date=session_date,
        day=day_from_index(session_date.weekday()),
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="",
        cohorts=(f"{code}-{group or aid}",),
        turn=turn,
        fixed=fixed,
        teachers=teachers,
        shared_id=shared_id,
    )
    activity = Activity(
        id=aid,
        code=code,
        kind="TE",
        session_ids=(session.id,),
        students=10,
        turn=turn,
        fixed=fixed,
        teachers=teachers,
        cohorts=session.cohorts,
        duration_min=duration,
    )
    return session, activity


def _data(
    pairs: list[tuple[Session, Activity]],
    *,
    days_without_class: frozenset[date] = frozenset(),
    general_rooms: int = 0,
) -> TimetableData:
    rooms = {f"A{i}": Room(f"A{i}", "A", "Aules docents", 40) for i in range(general_rooms)}
    return TimetableData(
        sessions={s.id: s for s, _ in pairs},
        rooms=rooms,
        activities={a.id: a for _, a in pairs},
        days_without_class=days_without_class,
        order=tuple(a.id for _, a in pairs),
    )


def _result(placements: dict[str, tuple[str, int]]) -> Phase1Result:
    return Phase1Result(
        ok=True,
        activity_day={aid: day for aid, (day, _) in placements.items()},
        activity_start={aid: start for aid, (_, start) in placements.items()},
        status="TEST",
        message="",
    )


def _rules(violations: list[Violation]) -> list[str]:
    return [v.rule for v in violations]


TEACHER = frozenset({"T1"})


def test_clean_result_has_no_violations() -> None:
    data = _data([_pair("A", teachers=TEACHER), _pair("B", teachers=TEACHER)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", TEN)})) == []


def test_missing_activity_is_reported() -> None:
    data = _data([_pair("A"), _pair("B")])
    violations = validate_phase1(data, _result({"A": ("L", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("MISSING", ("B",))]


def test_unknown_day_letter_is_missing() -> None:
    data = _data([_pair("A")])
    violations = validate_phase1(data, _result({"A": ("Z", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("MISSING", ("A",))]


def test_start_outside_turn_is_d1() -> None:
    data = _data([_pair("A", turn="mati")])
    violations = validate_phase1(data, _result({"A": ("L", FOUR_PM)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D1-TURN", ("A",))]


def test_day_without_class_is_d2() -> None:
    tuesday = MONDAY + timedelta(days=1)
    data = _data([_pair("A")], days_without_class=frozenset({tuesday}))
    violations = validate_phase1(data, _result({"A": ("M", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D2-CALENDAR", ("A",))]


def test_moved_pinned_activity_is_d3() -> None:
    data = _data([_pair("A", fixed="R1")])
    violations = validate_phase1(data, _result({"A": ("M", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D3-PINNED", ("A",))]


def test_pinned_activity_at_partida_is_clean() -> None:
    data = _data([_pair("A", fixed="R7", start=FOUR_PM)])
    assert validate_phase1(data, _result({"A": ("L", FOUR_PM)})) == []


def test_teacher_overlap_is_d4() -> None:
    data = _data([_pair("A", teachers=TEACHER), _pair("B", teachers=TEACHER, duration=120, start=FOUR_PM)])
    violations = validate_phase1(data, _result({"A": ("L", TEN), "B": ("L", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D4-CLASH", ("A", "B"))]


def test_d4_sweep_finds_clash_past_a_short_neighbour() -> None:
    data = _data(
        [
            _pair("LONG", teachers=TEACHER, duration=180),
            _pair("SHORT", duration=30),
            _pair("LATE", teachers=TEACHER, start=FOUR_PM),
        ]
    )
    result = _result({"LONG": ("L", NINE), "SHORT": ("L", NINE), "LATE": ("L", 11 * 60)})
    violations = validate_phase1(data, result)
    assert [(v.rule, v.activity_ids) for v in violations] == [("D4-CLASH", ("LATE", "LONG"))]


def test_pinned_pinned_clash_is_inherited_and_not_reported() -> None:
    data = _data([_pair("A", teachers=TEACHER, fixed="R1"), _pair("B", teachers=TEACHER, fixed="R7")])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)})) == []


def test_pinned_movable_clash_is_reported() -> None:
    data = _data([_pair("A", teachers=TEACHER, fixed="R1"), _pair("B", teachers=TEACHER, start=TEN)])
    violations = validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)}))
    assert _rules(violations) == ["D4-CLASH"]


def test_different_iso_weeks_do_not_clash() -> None:
    data = _data([_pair("A", teachers=TEACHER), _pair("B", teachers=TEACHER, session_date=NEXT_MONDAY)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)})) == []


def test_non_interacting_overlap_is_clean() -> None:
    data = _data([_pair("A"), _pair("B")])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)})) == []


def test_shared_id_at_different_slots_is_d5() -> None:
    data = _data([_pair("A", shared_id="X"), _pair("B", shared_id="X")])
    violations = validate_phase1(data, _result({"A": ("L", NINE), "B": ("M", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D5-SHARED", ("A", "B"))]


def test_shared_id_with_disjoint_domains_is_skipped() -> None:
    data = _data([_pair("A", shared_id="X", turn="mati"), _pair("B", shared_id="X", turn="tarda", start=FOUR_PM)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", FOUR_PM)})) == []


def test_shared_id_same_slot_is_clean_and_not_a_clash() -> None:
    data = _data([_pair("A", shared_id="X", teachers=TEACHER), _pair("B", shared_id="X", teachers=TEACHER)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)})) == []


def test_shared_two_pinned_at_different_slots_is_not_d5() -> None:
    data = _data([_pair("A", shared_id="X", fixed="R1"), _pair("B", shared_id="X", fixed="R1", start=11 * 60)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", 11 * 60)})) == []


def test_shared_movable_is_checked_only_against_pinned_root() -> None:
    data = _data(
        [
            _pair("A", shared_id="X", fixed="R1"),
            _pair("B", shared_id="X"),
            _pair("C", shared_id="X", fixed="R1", start=11 * 60),
        ]
    )
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE), "C": ("L", 11 * 60)})) == []
    violations = validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", 11 * 60), "C": ("L", 11 * 60)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D5-SHARED", ("A", "B"))]


def test_shared_movable_outside_pinned_out_of_turn_slot_is_skipped() -> None:
    # Pinned A sits outside its turn; CP-SAT pins it at partida, which B (tarda) cannot reach, so no link.
    data = _data([_pair("A", shared_id="X", fixed="R1", turn="tarda"), _pair("B", shared_id="X", turn="tarda")])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", FOUR_PM)})) == []


def test_shared_links_match_cpsat_links() -> None:
    data = _data(
        [
            _pair("A", shared_id="X", fixed="R1"),
            _pair("B", shared_id="X"),
            _pair("C", shared_id="X", fixed="R1", start=11 * 60),
        ]
    )
    result = solve_phase1(data, max_time_s=10, random_seed=0, num_workers=1)
    assert result.ok
    assert validate_phase1(data, result) == []


def _siblings() -> TimetableData:
    return _data(
        [_pair("A", code="C1", group="G/101"), _pair("B", code="C1", group="G/101")],
        general_rooms=0,
    )


def test_rules_none_skips_d6_and_d7() -> None:
    result = _result({"A": ("L", NINE), "B": ("L", 11 * 60)})
    assert validate_phase1(_siblings(), result) == []


def test_rules_enabled_report_d6_and_d7_sorted() -> None:
    result = _result({"A": ("L", NINE), "B": ("L", 11 * 60)})
    violations = validate_phase1(_siblings(), result, Phase1Rules())
    assert set(_rules(violations[:-1])) == {"D6-POOL"}
    assert (violations[-1].rule, violations[-1].activity_ids) == ("D7-SAME-KIND-DAY", ("A", "B"))
    keys = [(v.rule, v.activity_ids) for v in violations]
    assert keys == sorted(keys)


@pytest.mark.parametrize(
    ("rules", "expected"),
    [
        (Phase1Rules(same_kind_day=False, room_pools=False), set()),
        (Phase1Rules(same_kind_day=True, room_pools=False), {"D7-SAME-KIND-DAY"}),
        (Phase1Rules(same_kind_day=False, room_pools=True), {"D6-POOL"}),
    ],
)
def test_rules_flags_are_respected(rules: Phase1Rules, expected: set[str]) -> None:
    result = _result({"A": ("L", NINE), "B": ("L", 11 * 60)})
    assert set(_rules(validate_phase1(_siblings(), result, rules))) == expected


def test_output_is_sorted_by_rule_and_ids() -> None:
    data = _data([_pair("Z", turn="mati"), _pair("A"), _pair("M", fixed="R1")])
    violations = validate_phase1(data, _result({"Z": ("L", FOUR_PM), "M": ("X", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [
        ("D1-TURN", ("Z",)),
        ("D3-PINNED", ("M",)),
        ("MISSING", ("A",)),
    ]


def test_mini_paquet_greedy_validates_clean() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    assert validate_phase1(data, solve_phase1_greedy(data)) == []


def test_mini_paquet_cpsat_validates_clean() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30, random_seed=0, num_workers=1)
    assert result.ok
    assert validate_phase1(data, result) == []


def test_movable_pair_overlapping_in_partida_is_inherited_and_not_reported() -> None:
    data = _data([_pair("A", teachers=TEACHER), _pair("B", teachers=TEACHER, start=NINE + 30)])
    assert validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE)})) == []


def test_inherited_pair_does_not_hide_a_non_inherited_clash() -> None:
    data = _data(
        [
            _pair("A", teachers=TEACHER),
            _pair("B", teachers=TEACHER, start=NINE + 30),
            _pair("C", teachers=TEACHER, start=11 * 60),
        ]
    )
    violations = validate_phase1(data, _result({"A": ("L", NINE), "B": ("L", NINE), "C": ("L", NINE)}))
    assert [(v.rule, v.activity_ids) for v in violations] == [("D4-CLASH", ("A", "C")), ("D4-CLASH", ("B", "C"))]
