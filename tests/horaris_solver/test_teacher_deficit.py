from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from horaris_solver.domain.models import Assignment, Session, TimetableData
from horaris_solver.solver.teacher_deficit import (
    PLACEHOLDER_PREFIX,
    DeficitRow,
    assign_placeholders,
    compute_deficit,
    write_deficit_csv,
)

MONDAY = date(2025, 9, 15)
TUESDAY = date(2025, 9, 16)


def _session(
    sid: str,
    *,
    start: int = 9 * 60,
    duration: int = 60,
    code: str = "101",
    kind: str = "TE",
    teachers: frozenset[str] = frozenset(),
    shared_id: str = "",
    session_date: date = MONDAY,
) -> Session:
    return Session(
        id=sid,
        activity_id=f"A{sid}",
        code=code,
        kind=kind,
        group=f"{code}/{kind}/1",
        session_date=session_date,
        day="L",
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="R1",
        cohorts=(),
        turn="M",
        fixed="",
        teachers=teachers,
        shared_id=shared_id,
    )


def _data(*sessions: Session) -> TimetableData:
    return TimetableData(sessions={s.id: s for s in sessions}, rooms={}, activities={})


def _assign(session: Session, *, day: str = "L", start: int | None = None) -> Assignment:
    return Assignment(
        session_id=session.id,
        day=day,
        start_min=session.start_min if start is None else start,
        room="R1",
    )


def test_four_parallel_sessions_with_three_teachers_give_deficit_one() -> None:
    sessions = [_session(f"s{i}", teachers=frozenset({f"T{i}"}) if i < 3 else frozenset()) for i in range(4)]
    rows = compute_deficit(_data(*sessions), [_assign(s) for s in sessions])
    assert rows == (
        DeficitRow(
            code="101",
            kind="TE",
            max_simultaneous=4,
            real_teachers=3,
            deficit=1,
            peak_date=MONDAY,
            peak_start=9 * 60,
        ),
    )


def test_sequential_sessions_have_k_one() -> None:
    sessions = [_session(f"s{i}", start=9 * 60 + i * 120) for i in range(3)]
    (row,) = compute_deficit(_data(*sessions), [_assign(s) for s in sessions])
    assert row.max_simultaneous == 1
    assert row.deficit == 1


def test_touching_intervals_do_not_overlap() -> None:
    first = _session("a", start=9 * 60, duration=60)
    second = _session("b", start=10 * 60, duration=60)
    (row,) = compute_deficit(_data(first, second), [_assign(first), _assign(second)])
    assert row.max_simultaneous == 1


def test_shared_unit_counted_once() -> None:
    sessions = [_session(f"s{i}", shared_id="U1", teachers=frozenset({"T"})) for i in range(3)]
    (row,) = compute_deficit(_data(*sessions), [_assign(s) for s in sessions])
    assert row.max_simultaneous == 1
    assert row.deficit == 0


def test_shared_unit_at_separate_starts_is_not_merged_into_envelope() -> None:
    morning = _session("m", shared_id="U1", start=9 * 60)
    noon = _session("n", shared_id="U1", start=12 * 60)
    gap = _session("g", start=10 * 60 + 30)
    (row,) = compute_deficit(_data(morning, noon, gap), [])
    assert row.max_simultaneous == 1


def test_shared_unit_same_start_different_durations_counts_once() -> None:
    short = _session("a", shared_id="U1", duration=60)
    long = _session("b", shared_id="U1", duration=120)
    later = _session("c", start=10 * 60 + 30)
    (row,) = compute_deficit(_data(short, long, later), [])
    assert (row.max_simultaneous, row.peak_start) == (2, 10 * 60 + 30)


def test_placeholders_for_shared_unit_at_separate_starts_use_k_labels() -> None:
    morning = _session("m", shared_id="U1", start=9 * 60)
    noon = _session("n", shared_id="U1", start=12 * 60)
    gap = _session("g", start=10 * 60 + 30)
    labels = assign_placeholders(_data(morning, noon, gap), [])
    assert set(labels) == {"m", "n", "g"}
    assert set(labels.values()) == {"PENDENT-101-TE-1"}


def test_assignment_day_remaps_within_iso_week() -> None:
    a = _session("a")
    b = _session("b", session_date=TUESDAY)
    rows = compute_deficit(_data(a, b), [_assign(a), _assign(b, day="L")])
    assert rows[0].max_simultaneous == 2
    assert rows[0].peak_date == MONDAY


def test_assignment_start_overrides_partida() -> None:
    a = _session("a")
    b = _session("b")
    (row,) = compute_deficit(_data(a, b), [_assign(a), _assign(b, start=11 * 60)])
    assert row.max_simultaneous == 1


def test_peak_reports_date_and_start() -> None:
    a = _session("a", session_date=TUESDAY, start=12 * 60)
    b = _session("b", session_date=TUESDAY, start=12 * 60 + 30)
    c = _session("c", session_date=MONDAY, start=8 * 60 + 30)
    (row,) = compute_deficit(_data(a, b, c), [])
    assert (row.max_simultaneous, row.peak_date, row.peak_start) == (2, TUESDAY, 12 * 60 + 30)


def test_groups_by_code_and_kind() -> None:
    a = _session("a", code="101", kind="TE")
    b = _session("b", code="101", kind="PLAB")
    c = _session("c", code="202", kind="TE", teachers=frozenset({"X"}))
    rows = compute_deficit(_data(a, b, c), [])
    assert [(r.code, r.kind, r.max_simultaneous, r.deficit) for r in rows] == [
        ("101", "PLAB", 1, 1),
        ("101", "TE", 1, 1),
        ("202", "TE", 1, 0),
    ]


def test_empty_input_returns_empty_tuple() -> None:
    assert compute_deficit(_data(), []) == ()
    assert assign_placeholders(_data(), []) == {}


INTERVAL_SETS: list[list[tuple[int, int]]] = [
    [(0, 60), (30, 90), (60, 120), (90, 150)],
    [(0, 100), (10, 20), (20, 30), (30, 40), (50, 120)],
    [(0, 30), (0, 30), (0, 30), (30, 60)],
    [(0, 240), (60, 120), (90, 180), (150, 300), (200, 210)],
    [(500, 560)],
]


@pytest.mark.parametrize("intervals", INTERVAL_SETS)
def test_colouring_uses_exactly_k_colours(intervals: list[tuple[int, int]]) -> None:
    sessions = [_session(f"s{i}", start=s, duration=e - s) for i, (s, e) in enumerate(intervals)]
    data = _data(*sessions)
    (row,) = compute_deficit(data, [])
    labels = assign_placeholders(data, [])
    assert set(labels) == {s.id for s in sessions}
    assert len(set(labels.values())) == row.max_simultaneous
    for i, left in enumerate(sessions):
        for right in sessions[i + 1 :]:
            if left.start_min < right.end_min and right.start_min < left.end_min:
                assert labels[left.id] != labels[right.id]


def test_label_format_and_numbering_starts_at_one() -> None:
    a = _session("a", code="101", kind="TE")
    labels = assign_placeholders(_data(a), [])
    assert labels == {"a": f"{PLACEHOLDER_PREFIX}-101-TE-1"}


def test_labels_stable_per_shared_unit() -> None:
    sessions = [_session(f"s{i}", shared_id="U1") for i in range(3)]
    other = _session("o")
    labels = assign_placeholders(_data(*sessions, other), [])
    assert len({labels[s.id] for s in sessions}) == 1
    assert labels["o"] != labels["s0"]


def test_only_sessions_without_teachers_get_placeholders() -> None:
    staffed = _session("a", teachers=frozenset({"T"}))
    empty = _session("b")
    assert assign_placeholders(_data(staffed, empty), []) == {"b": "PENDENT-101-TE-1"}


def test_colours_reused_across_dates() -> None:
    a = _session("a", session_date=MONDAY)
    b = _session("b", session_date=TUESDAY)
    labels = assign_placeholders(_data(a, b), [])
    assert labels["a"] == labels["b"] == "PENDENT-101-TE-1"


def test_placeholder_never_equals_real_teacher_name() -> None:
    clash = _session("x", code="999", teachers=frozenset({"PENDENT-101-TE-1"}))
    a = _session("a")
    b = _session("b")
    labels = assign_placeholders(_data(clash, a, b), [])
    assert sorted(labels.values()) == ["PENDENT-101-TE-2", "PENDENT-101-TE-3"]


def test_write_csv_roundtrip(tmp_path: Path) -> None:
    rows = (
        DeficitRow("101", "TE", 4, 3, 1, MONDAY, 9 * 60),
        DeficitRow("Àlgebra", "PLAB", 1, 2, 0, TUESDAY, 15 * 60 + 30),
    )
    path = tmp_path / "deficit_docents.csv"
    write_deficit_csv(path, rows)
    with path.open(encoding="utf-8", newline="") as handle:
        read = list(csv.reader(handle))
    assert read == [
        ["codi", "tipus", "max_simultanies", "docents_reals", "deficit", "data_pic", "franja_pic"],
        ["101", "TE", "4", "3", "1", "2025-09-15", "09:00"],
        ["Àlgebra", "PLAB", "1", "2", "0", "2025-09-16", "15:30"],
    ]


def test_write_csv_empty_writes_header_only(tmp_path: Path) -> None:
    path = tmp_path / "d.csv"
    write_deficit_csv(path, ())
    assert path.read_text(encoding="utf-8").splitlines() == [
        "codi,tipus,max_simultanies,docents_reals,deficit,data_pic,franja_pic"
    ]
