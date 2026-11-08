"""Read-only data measurement: aggregate integer counts only (T0.1).

The paquet is pseudonymised, not anonymised, so this module never emits names,
codes, teachers or rows: every metric is a non-negative integer.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path

from horaris_solver.domain.models import Activity, Session, TimetableData
from horaris_solver.solver.conflicts import cohort_clash, plab_blocks, same_teaching_event

PINNED_PREFIXES = ("R1", "R7")
_PLACEHOLDER_SUBSTRINGS = ("PENDENT", "PENDIENTE", "?", "TBD", "VACANT")
_PLACEHOLDER_TOKEN = re.compile(r"(?<![A-Z0-9])NN(?![A-Z0-9])")

METRIC_KEYS = (
    "sessions",
    "activities",
    "sessions_without_activity",
    "pinned_activities",
    "movable_activities",
    "heterogeneous_activities",
    "same_kind_day_pairs_fixed_fixed",
    "same_kind_day_pairs_mixed",
    "same_kind_day_pairs_movable_movable",
    "partida_conflict_pairs_teacher",
    "partida_conflict_pairs_cohort",
    "partida_conflict_pairs_plab",
    "sessions_teachers_0",
    "sessions_teachers_1",
    "sessions_teachers_2",
    "sessions_teachers_3plus",
    "teacher_deficit_subject_kinds",
    "teacher_deficit_total",
    "pending_marker_sessions",
)


def is_pinned(activity: Activity) -> bool:
    return activity.fixed.startswith(PINNED_PREFIXES)


def is_placeholder_teacher(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _PLACEHOLDER_SUBSTRINGS) or bool(_PLACEHOLDER_TOKEN.search(upper))


def _activity_sessions(data: TimetableData) -> dict[str, list[Session]]:
    grouped: dict[str, list[Session]] = defaultdict(list)
    for session in data.sessions.values():
        if session.activity_id in data.activities:
            grouped[session.activity_id].append(session)
    return grouped


def _heterogeneous_count(grouped: dict[str, list[Session]]) -> int:
    count = 0
    for sessions in grouped.values():
        shapes = {(s.day, s.start_min, s.duration_min, s.fixed) for s in sessions}
        if len(shapes) > 1:
            count += 1
    return count


def _ordered(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _same_kind_day_pairs(data: TimetableData) -> dict[str, int]:
    buckets: dict[tuple[date, str, str, str], set[str]] = defaultdict(set)
    for session in data.sessions.values():
        if session.activity_id in data.activities:
            key = (session.session_date, session.group, session.code, session.kind)
            buckets[key].add(session.activity_id)
    pairs: set[tuple[str, str]] = set()
    for activity_ids in buckets.values():
        ordered = sorted(activity_ids)
        for i, first_id in enumerate(ordered):
            for second_id in ordered[i + 1 :]:
                pairs.add((first_id, second_id))
    counts = {"fixed_fixed": 0, "mixed": 0, "movable_movable": 0}
    for left_id, right_id in pairs:
        left, right = data.activities[left_id], data.activities[right_id]
        if same_teaching_event(left, right, data):
            continue
        pinned = is_pinned(left) + is_pinned(right)
        counts[("movable_movable", "mixed", "fixed_fixed")[pinned]] += 1
    return {f"same_kind_day_pairs_{name}": value for name, value in counts.items()}


def _overlapping_session_pairs(sessions: Iterable[Session]) -> Iterator[tuple[Session, Session]]:
    """Sweep sessions of one date sorted by start; yield pairs whose times overlap."""
    active: list[Session] = []
    for session in sorted(sessions, key=lambda s: s.start_min):
        active = [other for other in active if other.end_min > session.start_min]
        for other in active:
            yield other, session
        active.append(session)


def _partida_conflict_pairs(data: TimetableData) -> dict[str, int]:
    by_date: dict[date, list[Session]] = defaultdict(list)
    for session in data.sessions.values():
        if session.activity_id in data.activities:
            by_date[session.session_date].append(session)
    overlapping: set[tuple[str, str]] = set()
    for sessions in by_date.values():
        for first, second in _overlapping_session_pairs(sessions):
            if first.activity_id != second.activity_id:
                overlapping.add(_ordered(first.activity_id, second.activity_id))
    counts = {"teacher": 0, "cohort": 0, "plab": 0}
    for left_id, right_id in overlapping:
        left, right = data.activities[left_id], data.activities[right_id]
        if same_teaching_event(left, right, data):
            continue
        if left.teachers & right.teachers:
            counts["teacher"] += 1
        if set(left.cohorts) & set(right.cohorts) and cohort_clash(left, right, data):
            counts["cohort"] += 1
        if plab_blocks(left, right):
            counts["plab"] += 1
    return {f"partida_conflict_pairs_{name}": value for name, value in counts.items()}


def _teacher_histogram(data: TimetableData) -> dict[str, int]:
    counts = {"0": 0, "1": 0, "2": 0, "3plus": 0}
    for session in data.sessions.values():
        size = len(session.teachers)
        counts[str(size) if size < 3 else "3plus"] += 1
    return {f"sessions_teachers_{name}": value for name, value in counts.items()}


def _pending_marker_sessions(data: TimetableData) -> int:
    return sum(1 for s in data.sessions.values() if any(is_placeholder_teacher(t) for t in s.teachers))


def _max_simultaneous_units(sessions: list[Session]) -> int:
    """Interval clique size on one date, counting each id_compartida unit once."""
    intervals: dict[str, tuple[int, int]] = {}
    for session in sessions:
        start, end = intervals.get(session.unit, (session.start_min, session.end_min))
        intervals[session.unit] = (min(start, session.start_min), max(end, session.end_min))
    events = sorted([(start, 1) for start, _ in intervals.values()] + [(end, -1) for _, end in intervals.values()])
    best = current = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


def _teacher_deficit(data: TimetableData) -> dict[str, int]:
    by_subject_date: dict[tuple[str, str], dict[date, list[Session]]] = defaultdict(lambda: defaultdict(list))
    real_teachers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for session in data.sessions.values():
        subject = (session.code, session.kind)
        by_subject_date[subject][session.session_date].append(session)
        real_teachers[subject].update(t for t in session.teachers if not is_placeholder_teacher(t))
    kinds = total = 0
    for subject, per_date in by_subject_date.items():
        peak = max(_max_simultaneous_units(sessions) for sessions in per_date.values())
        deficit = max(0, peak - len(real_teachers[subject]))
        if deficit:
            kinds += 1
            total += deficit
    return {"teacher_deficit_subject_kinds": kinds, "teacher_deficit_total": total}


def measure(data: TimetableData) -> dict[str, int]:
    """Return aggregate, non-identifying integer metrics for the loaded data."""
    grouped = _activity_sessions(data)
    pinned = sum(1 for a in data.activities.values() if is_pinned(a))
    metrics: dict[str, int] = {
        "sessions": len(data.sessions),
        "activities": len(data.activities),
        "sessions_without_activity": sum(1 for s in data.sessions.values() if s.activity_id not in data.activities),
        "pinned_activities": pinned,
        "movable_activities": len(data.activities) - pinned,
        "heterogeneous_activities": _heterogeneous_count(grouped),
    }
    metrics.update(_same_kind_day_pairs(data))
    metrics.update(_partida_conflict_pairs(data))
    metrics.update(_teacher_histogram(data))
    metrics.update(_teacher_deficit(data))
    metrics["pending_marker_sessions"] = _pending_marker_sessions(data)
    return {key: metrics[key] for key in METRIC_KEYS}


def to_markdown(metrics: dict[str, int], *, title: str) -> str:
    lines = [f"### {title}", "", "| Metric | Value |", "|---|---:|"]
    lines.extend(f"| `{key}` | {value} |" for key, value in metrics.items())
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m horaris_solver.audit.measure", description=__doc__)
    parser.add_argument("--paquet", type=Path, required=True, help="Directory with the paquet CSVs")
    parser.add_argument("--semestre", type=int, choices=(1, 2), default=None)
    parser.add_argument("--curs", default=None, help="Comma-separated grades filter: 1r,2n,...")
    parser.add_argument("--out-md", type=Path, default=None, help="Write the aggregate table as Markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    from horaris_solver.adapters.csv_loader import CsvTimetableSource
    from horaris_solver.domain.filters import parse_cursos

    args = build_parser().parse_args(argv)
    try:
        cursos = parse_cursos(args.curs)
    except ValueError as exc:
        print(f"invalid --curs: {exc}", file=sys.stderr)
        return 2
    if not (args.paquet / "sessions.csv").is_file():
        print("paquet not found or missing sessions.csv", file=sys.stderr)
        return 2
    data = CsvTimetableSource(args.paquet).load(semestre=args.semestre, cursos=cursos)
    metrics = measure(data)
    title = f"semestre={args.semestre or '*'} curs={args.curs or '*'}"
    table = to_markdown(metrics, title=title)
    print(table, end="")
    if args.out_md is not None:
        args.out_md.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
