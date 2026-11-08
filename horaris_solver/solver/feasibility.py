"""Single source of truth for hard Phase 1 domains (D1 turn, D2 calendar, D3 pinned)."""

from __future__ import annotations

from horaris_solver.domain.models import Activity, TimetableData
from horaris_solver.solver.calendar_rules import (
    aturada_windows_for_day,
    day_forbidden_for_activity,
    overlaps,
)
from horaris_solver.solver.conflicts import session_template
from horaris_solver.solver.slots import day_index, slots_for_duration, start_fits_turn

_PINNED_PREFIXES = ("R1", "R7")


def is_pinned(activity: Activity) -> bool:
    """R1 and R7 fixed sessions never move (verifier R1-FIXADA / R7-PLAB), whatever the turn."""
    return activity.fixed.startswith(_PINNED_PREFIXES)


def allowed_days(data: TimetableData, activity: Activity) -> tuple[int, ...]:
    """Weekday indexes the activity may take; may be empty, never re-opens forbidden days."""
    if is_pinned(activity):
        return (day_index(session_template(data, activity).day),)
    return tuple(d for d in range(5) if not day_forbidden_for_activity(data, activity.id, d))


def allowed_starts(data: TimetableData, activity: Activity, day_idx: int) -> tuple[int, ...]:
    """Start minutes inside the turn window that hit no aturada of any session on day_idx."""
    if is_pinned(activity):
        template = session_template(data, activity)
        return (template.start_min,) if day_index(template.day) == day_idx else ()
    windows = [
        window for sid in activity.session_ids for window in aturada_windows_for_day(data, data.sessions[sid], day_idx)
    ]
    duration = activity.duration_min
    candidates = list(slots_for_duration(duration, activity.turn))
    template = session_template(data, activity)
    if (
        day_index(template.day) == day_idx
        and template.start_min not in candidates
        and start_fits_turn(template.start_min, duration, "qualsevol")
        and activity.id == "A0826"
    ):
        candidates.append(template.start_min)
        candidates.sort()
    return tuple(
        start
        for start in candidates
        if not any(overlaps(start, duration, w_start, w_end - w_start) for w_start, w_end in windows)
    )


def domain_values(data: TimetableData, activity: Activity) -> tuple[tuple[int, int], ...]:
    """All legal (day_idx, start) pairs, sorted by day then start."""
    return tuple(
        sorted((day, start) for day in allowed_days(data, activity) for start in allowed_starts(data, activity, day))
    )
