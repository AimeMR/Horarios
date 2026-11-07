"""Calendar helpers matching the official verifier date remap."""

from __future__ import annotations

from datetime import date, timedelta

from horaris_solver.domain.models import Session, TimetableData
from horaris_solver.solver.slots import day_index


def week_monday(session_date: date) -> date:
    return session_date - timedelta(days=session_date.weekday())


def remap_date(session_date: date, new_day: str) -> date:
    """New date = chosen weekday inside the same ISO week as the partida date."""
    return session_date + timedelta(days=day_index(new_day) - session_date.weekday())


def remap_date_index(session_date: date, day_idx: int) -> date:
    return session_date + timedelta(days=day_idx - session_date.weekday())


def same_iso_week(a: date, b: date) -> bool:
    return week_monday(a) == week_monday(b)


def activities_share_iso_week(
    data: TimetableData,
    left_id: str,
    right_id: str,
) -> bool:
    left_sessions = [data.sessions[sid] for sid in data.activities[left_id].session_ids]
    right_sessions = [data.sessions[sid] for sid in data.activities[right_id].session_ids]
    return any(
        same_iso_week(a.session_date, b.session_date)
        for a in left_sessions
        for b in right_sessions
    )


def aturades_by_date(data: TimetableData) -> dict[date, list[tuple[int, int]]]:
    out: dict[date, list[tuple[int, int]]] = {}
    for block in data.calendar:
        out.setdefault(block.block_date, []).append((block.start_min, block.end_min))
    return out


def day_forbidden_for_activity(
    data: TimetableData,
    activity_id: str,
    day_idx: int,
) -> bool:
    """True if assigning this weekday would move any session onto dies_sense_classe."""
    activity = data.activities[activity_id]
    for sid in activity.session_ids:
        session = data.sessions[sid]
        new_date = remap_date_index(session.session_date, day_idx)
        if new_date != session.session_date and new_date in data.days_without_class:
            return True
    return False


def aturada_windows_for_day(
    data: TimetableData,
    session: Session,
    day_idx: int,
) -> list[tuple[int, int]]:
    """Aturada intervals that would apply if the session moved to day_idx (verifier semantics)."""
    new_date = remap_date_index(session.session_date, day_idx)
    windows = aturades_by_date(data).get(new_date, [])
    if not windows:
        return []
    # Exception: already on that aturada day in partida — hour changes same day allowed.
    if new_date == session.session_date:
        original_hit = any(
            session.start_min < end and session.end_min > start for start, end in windows
        )
        if original_hit:
            return []
    return windows


def overlaps(start_a: int, dur_a: int, start_b: int, dur_b: int) -> bool:
    return start_a < start_b + dur_b and start_b < start_a + dur_a
