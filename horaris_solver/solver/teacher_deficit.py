"""Post-solve teacher deficit report and placeholder teacher labels.

Placeholders never enter the solver. After solving, for each (code, kind) and
date the peak number of simultaneous units (max clique of the interval graph)
is compared with the number of distinct real teachers of that (code, kind).
"""

from __future__ import annotations

import csv
import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from horaris_solver.domain.models import Assignment, Session, TimetableData, fmt
from horaris_solver.solver.calendar_rules import remap_date

PLACEHOLDER_PREFIX = "PENDENT"
CSV_HEADER = ("codi", "tipus", "max_simultanies", "docents_reals", "deficit", "data_pic", "franja_pic")

GroupKey = tuple[str, str]
Interval = tuple[int, int, str]  # (start, end, unit)


@dataclass(frozen=True)
class DeficitRow:
    code: str
    kind: str
    max_simultaneous: int
    real_teachers: int
    deficit: int
    peak_date: date
    peak_start: int


def _placed(session: Session, assignment: Assignment | None) -> tuple[date, int]:
    if assignment is None:
        return session.session_date, session.start_min
    return remap_date(session.session_date, assignment.day), assignment.start_min


def _unit_intervals(
    data: TimetableData,
    assignments: list[Assignment],
    include: set[str] | None = None,
) -> dict[GroupKey, dict[date, list[Interval]]]:
    """Intervals per (code, kind) and date, one per (shared unit, start): same-unit sessions at one start count once."""
    by_id = {a.session_id: a for a in assignments}
    ends: dict[tuple[str, str, date, str, int], int] = {}
    for sid, session in data.sessions.items():
        if include is not None and sid not in include:
            continue
        day, start = _placed(session, by_id.get(sid))
        key = (session.code, session.kind, day, session.unit, start)
        ends[key] = max(ends.get(key, start), start + session.duration_min)
    out: dict[GroupKey, dict[date, list[Interval]]] = defaultdict(lambda: defaultdict(list))
    for (code, kind, day, unit, start), end in ends.items():
        out[(code, kind)][day].append((start, end, unit))
    return out


def _max_clique(intervals: list[Interval]) -> tuple[int, int]:
    """Sweep over endpoints; ends sort before starts at equal times. Returns (k, peak start)."""
    events = sorted([(s, 1) for s, _, _ in intervals] + [(e, -1) for _, e, _ in intervals])
    best, best_at, current = 0, 0, 0
    for time, delta in events:
        current += delta
        if current > best:
            best, best_at = current, time
    return best, best_at


def _real_teachers_by_group(data: TimetableData) -> dict[GroupKey, frozenset[str]]:
    teachers: dict[GroupKey, set[str]] = defaultdict(set)
    for session in data.sessions.values():
        teachers[(session.code, session.kind)].update(session.teachers)
    return {key: frozenset(names) for key, names in teachers.items()}


def compute_deficit(data: TimetableData, assignments: list[Assignment]) -> tuple[DeficitRow, ...]:
    teachers = _real_teachers_by_group(data)
    rows: list[DeficitRow] = []
    for (code, kind), per_date in sorted(_unit_intervals(data, assignments).items()):
        k_max, peak_date, peak_start = 0, date.min, 0
        for day in sorted(per_date):
            k, at = _max_clique(per_date[day])
            if k > k_max:
                k_max, peak_date, peak_start = k, day, at
        real = len(teachers.get((code, kind), frozenset()))
        rows.append(DeficitRow(code, kind, k_max, real, max(0, k_max - real), peak_date, peak_start))
    return tuple(rows)


def _greedy_colours(intervals: list[Interval]) -> dict[tuple[str, int], int]:
    """Interval colouring by start time; uses exactly max-clique colours. Returns (unit, start) -> colour (0-based)."""
    free: list[int] = []
    busy: list[tuple[int, int]] = []  # (end, colour)
    used = 0
    colours: dict[tuple[str, int], int] = {}
    for start, end, unit in sorted(intervals):
        while busy and busy[0][0] <= start:
            heapq.heappush(free, heapq.heappop(busy)[1])
        if free:
            colour = heapq.heappop(free)
        else:
            colour, used = used, used + 1
        colours[(unit, start)] = colour
        heapq.heappush(busy, (end, colour))
    return colours


def _labels(code: str, kind: str, count: int, reserved: frozenset[str]) -> list[str]:
    labels: list[str] = []
    n = 1
    while len(labels) < count:
        label = f"{PLACEHOLDER_PREFIX}-{code}-{kind}-{n}"
        if label not in reserved:
            labels.append(label)
        n += 1
    return labels


def assign_placeholders(data: TimetableData, assignments: list[Assignment]) -> dict[str, str]:
    """session_id -> placeholder label for every session without real teachers."""
    empty = {sid for sid, session in data.sessions.items() if not session.teachers}
    if not empty:
        return {}
    reserved = frozenset(name for session in data.sessions.values() for name in session.teachers)
    by_id = {a.session_id: a for a in assignments}
    intervals = _unit_intervals(data, assignments, include=empty)
    colours: dict[GroupKey, dict[date, dict[tuple[str, int], int]]] = {}
    labels: dict[GroupKey, list[str]] = {}
    for (code, kind), per_date in intervals.items():
        colours[(code, kind)] = {day: _greedy_colours(items) for day, items in per_date.items()}
        n_colours = max(max(c.values()) + 1 for c in colours[(code, kind)].values())
        labels[(code, kind)] = _labels(code, kind, n_colours, reserved)
    out: dict[str, str] = {}
    for sid in empty:
        session = data.sessions[sid]
        group = (session.code, session.kind)
        day, start = _placed(session, by_id.get(sid))
        out[sid] = labels[group][colours[group][day][(session.unit, start)]]
    return out


def write_deficit_csv(path: Path, rows: tuple[DeficitRow, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(
                (
                    row.code,
                    row.kind,
                    row.max_simultaneous,
                    row.real_teachers,
                    row.deficit,
                    row.peak_date.isoformat(),
                    fmt(row.peak_start),
                )
            )
