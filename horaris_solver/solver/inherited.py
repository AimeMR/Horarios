"""Activity pairs whose clash is inherited from partida (verifier: ``heretada='partida'``).

The official verifier keys inherited R4 violations by (rule, session pair), whatever the final time, so a
pair of interacting activities whose sessions already overlap in partida on the same date never counts as
a new violation. Pure Python (no ortools): shared by CP-SAT, greedy, repair and the validator.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from horaris_solver.domain.models import Session, TimetableData
from horaris_solver.solver.conflicts import activities_interact

ActivityPair = tuple[str, str]


def _sessions_by_date(data: TimetableData) -> dict[date, list[Session]]:
    by_date: dict[date, list[Session]] = defaultdict(list)
    for session in data.sessions.values():
        if session.activity_id in data.activities:
            by_date[session.session_date].append(session)
    return by_date


def _overlapping_activity_ids(sessions: list[Session]) -> set[ActivityPair]:
    """(a, b) with a < b for sessions of different activities overlapping on one date (start-sorted sweep)."""
    found: set[ActivityPair] = set()
    active: list[Session] = []
    for session in sorted(sessions, key=lambda s: (s.start_min, s.id)):
        active = [other for other in active if other.end_min > session.start_min]
        for other in active:
            if other.activity_id != session.activity_id:
                low, high = sorted((other.activity_id, session.activity_id))
                found.add((low, high))
        active.append(session)
    return found


def partida_overlap_pairs(data: TimetableData) -> frozenset[ActivityPair]:
    """Sorted activity-id pairs that interact and whose sessions overlap in partida on the same date."""
    candidates: set[ActivityPair] = set()
    for sessions in _sessions_by_date(data).values():
        candidates |= _overlapping_activity_ids(sessions)
    return frozenset(
        (low, high)
        for low, high in candidates
        if activities_interact(data.activities[low], data.activities[high], data)
    )


def is_inherited_pair(pairs: frozenset[ActivityPair], left: str, right: str) -> bool:
    """True when the (unordered) activity pair is in ``pairs``."""
    return (left, right) in pairs if left < right else (right, left) in pairs
