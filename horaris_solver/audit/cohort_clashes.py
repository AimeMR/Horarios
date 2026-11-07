"""Detect same-cohort student clashes (two classes at once for the same grade line)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from horaris_solver.domain.models import Assignment, Session, TimetableData, fmt
from horaris_solver.solver.calendar_rules import remap_date
from horaris_solver.solver.conflicts import sessions_cohort_clash


@dataclass(frozen=True)
class CohortClash:
    cohort_key: str
    on_date: date
    left_id: str
    right_id: str
    left_start: int
    left_end: int
    right_start: int
    right_end: int

    def summary(self) -> str:
        return (
            f"{self.on_date.isoformat()} {self.cohort_key}: "
            f"{self.left_id} {fmt(self.left_start)}-{fmt(self.left_end)} × "
            f"{self.right_id} {fmt(self.right_start)}-{fmt(self.right_end)}"
        )


def _groups_clash(left: Session, right: Session) -> bool:
    """Same semantics as phase1 cohort clash (shared cohort + TE line / group number)."""
    return sessions_cohort_clash(left, right)


def find_cohort_clashes(
    data: TimetableData,
    assignments: list[Assignment] | None = None,
    *,
    use_partida: bool = False,
) -> list[CohortClash]:
    if assignments is None and not use_partida:
        raise ValueError("pass assignments=... or use_partida=True")

    by_id = {a.session_id: a for a in assignments} if assignments is not None else {}
    placed: list[tuple[Session, date, int, int]] = []
    for session in data.sessions.values():
        if use_partida:
            on_date = session.session_date
            start = session.start_min
            end = session.end_min
        else:
            assignment = by_id.get(session.id)
            if assignment is None:
                continue
            on_date = remap_date(session.session_date, assignment.day)
            start = assignment.start_min
            end = start + session.duration_min
        placed.append((session, on_date, start, end))

    by_date: dict[date, list[tuple[Session, int, int]]] = defaultdict(list)
    for session, on_date, start, end in placed:
        by_date[on_date].append((session, start, end))

    clashes: list[CohortClash] = []
    seen: set[tuple[str, str, str]] = set()
    for on_date, items in by_date.items():
        items.sort(key=lambda row: row[1])
        for i, (left, left_start, left_end) in enumerate(items):
            for right, right_start, right_end in items[i + 1 :]:
                if left_end <= right_start:
                    break
                if right_end <= left_start:
                    continue
                if left.unit == right.unit:
                    continue
                if not _groups_clash(left, right):
                    continue
                pair = tuple(sorted((left.id, right.id)))
                key = (on_date.isoformat(), pair[0], pair[1])
                if key in seen:
                    continue
                seen.add(key)
                shared = sorted(set(left.cohorts) & set(right.cohorts))
                clashes.append(
                    CohortClash(
                        cohort_key="|".join(shared) or "?",
                        on_date=on_date,
                        left_id=left.id,
                        right_id=right.id,
                        left_start=left_start,
                        left_end=left_end,
                        right_start=right_start,
                        right_end=right_end,
                    )
                )
    clashes.sort(key=lambda c: (c.on_date, c.cohort_key, c.left_id, c.right_id))
    return clashes
