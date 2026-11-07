"""Shared clash predicates for phase1 CP-SAT and greedy repair."""

from __future__ import annotations

from horaris_solver.domain.models import Activity, Session, TimetableData


def session_template(data: TimetableData, activity: Activity) -> Session:
    return data.sessions[activity.session_ids[0]]


def sessions_cohort_clash(left: Session, right: Session) -> bool:
    """Shared cohort plus TE line / group-number rule (audit and phase1)."""
    if not set(left.cohorts) & set(right.cohorts):
        return False
    if left.kind == "TE" or right.kind == "TE":
        return bool(left.line == right.line or left.group_number == right.group_number)
    return bool(left.group_number == right.group_number)


def cohort_clash(left: Activity, right: Activity, data: TimetableData) -> bool:
    return sessions_cohort_clash(session_template(data, left), session_template(data, right))


def plab_blocks(left: Activity, right: Activity) -> bool:
    if left.code != right.code:
        return False
    kinds = {left.kind, right.kind}
    return "PLAB" in kinds and bool(kinds & {"TE", "PAUL"})


def shared_teaching_ids(activity: Activity, data: TimetableData) -> set[str]:
    return {
        data.sessions[sid].shared_id
        for sid in activity.session_ids
        if data.sessions[sid].shared_id
    }


def same_teaching_event(left: Activity, right: Activity, data: TimetableData) -> bool:
    """True when activities are co-scheduled via id_compartida (same physical class)."""
    return bool(shared_teaching_ids(left, data) & shared_teaching_ids(right, data))


def activities_interact(left: Activity, right: Activity, data: TimetableData) -> bool:
    if same_teaching_event(left, right, data):
        return False  # must share day/time, not compete
    if left.teachers & right.teachers:
        return True
    if set(left.cohorts) & set(right.cohorts) and cohort_clash(left, right, data):
        return True
    return plab_blocks(left, right)
