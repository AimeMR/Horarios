"""Phase 1: assign day + start time per activity (CP-SAT)."""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from horaris_solver.domain.models import MATI, TARDA, Activity, Assignment, TimetableData
from horaris_solver.solver.calendar_rules import (
    activities_share_iso_week,
    aturada_windows_for_day,
    day_forbidden_for_activity,
)
from horaris_solver.solver.conflicts import (
    cohort_clash,
    plab_blocks,
    same_teaching_event,
    session_template,
)
from horaris_solver.solver.slots import day_from_index, day_index, slots_for_duration
from horaris_solver.solver.soft_weights import (
    WEIGHT_CANVI_DIA,
    WEIGHT_CANVI_HORA,
    WEIGHT_HORES_MORTES,
)


def _fits_turn(start: int, duration: int, turn: str) -> bool:
    end = start + duration
    if turn == "mati":
        return MATI[0] <= start and end <= MATI[1]
    if turn == "tarda":
        return TARDA[0] <= start and end <= TARDA[1]
    return True


def _pin_activity(activity: Activity, data: TimetableData) -> bool:
    """Prefer pinning R7 PLAB only when partida already sits inside the turn.

    R1 fixed sessions are left movable so cohort clashes in partida can be repaired.
    """
    if not activity.fixed.startswith("R7"):
        return False
    template = session_template(data, activity)
    return _fits_turn(template.start_min, activity.duration_min, activity.turn)


@dataclass(frozen=True)
class Phase1Result:
    ok: bool
    activity_day: dict[str, str]
    activity_start: dict[str, int]
    status: str
    message: str
    objective: int = 0
    unplaced: tuple[str, ...] = ()


def _allowed_days(data: TimetableData, activity: Activity, *, pinned: bool) -> list[int]:
    if pinned:
        return [day_index(session_template(data, activity).day)]
    legal = [d for d in range(5) if not day_forbidden_for_activity(data, activity.id, d)]
    # Filtered loads over-forbid weekdays; keep a usable domain for packing.
    return legal if len(legal) >= 2 else list(range(5))


def _apply_phase1_hints(
    model: cp_model.CpModel,
    day_vars: dict[str, cp_model.IntVar],
    start_vars: dict[str, cp_model.IntVar],
    hints: Phase1Result | None,
) -> None:
    if hints is None:
        return
    for activity_id, day in hints.activity_day.items():
        day_var = day_vars.get(activity_id)
        if day_var is None:
            continue
        model.add_hint(day_var, day_index(day))
    for activity_id, start in hints.activity_start.items():
        start_var = start_vars.get(activity_id)
        if start_var is None:
            continue
        model.add_hint(start_var, start)


def solve_phase1(
    data: TimetableData,
    *,
    max_time_s: int = 150,
    hints: Phase1Result | None = None,
    stop_after_first_feasible: bool = False,
) -> Phase1Result:
    model = cp_model.CpModel()
    activities = list(data.activities.values())

    day_vars: dict[str, cp_model.IntVar] = {}
    start_vars: dict[str, cp_model.IntVar] = {}
    pinned_ids = {a.id for a in activities if _pin_activity(a, data)}

    for activity in activities:
        template = session_template(data, activity)
        if activity.id in pinned_ids:
            day_vars[activity.id] = model.NewConstant(day_index(template.day))
            start_vars[activity.id] = model.NewConstant(template.start_min)
            continue

        slots = slots_for_duration(activity.duration_min, activity.turn)
        allowed_days = _allowed_days(data, activity, pinned=False)
        if not slots or not allowed_days:
            return Phase1Result(
                False,
                {},
                {},
                "INFEASIBLE",
                f"no feasible day/slot for activity {activity.id}",
            )
        day_vars[activity.id] = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(allowed_days), f"day_{activity.id}"
        )
        start_vars[activity.id] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(slots), f"start_{activity.id}")

        # R2-CALENDARI aturades: if day==d, start must not overlap aturada windows
        for day_idx in allowed_days:
            forbidden_starts: set[int] = set()
            for sid in activity.session_ids:
                session = data.sessions[sid]
                for win_start, win_end in aturada_windows_for_day(data, session, day_idx):
                    for start in slots:
                        if start < win_end and start + activity.duration_min > win_start:
                            forbidden_starts.add(start)
            for start in forbidden_starts:
                # day==day_idx ⇒ start != forbidden
                use = model.NewBoolVar(f"atur_{activity.id}_{day_idx}_{start}")
                model.Add(day_vars[activity.id] == day_idx).OnlyEnforceIf(use)
                model.Add(day_vars[activity.id] != day_idx).OnlyEnforceIf(use.Not())
                model.Add(start_vars[activity.id] != start).OnlyEnforceIf(use)

    # Shared sessions (same id_compartida) must share day+time when domains allow it
    shared_groups: dict[str, list[str]] = {}
    for session in data.sessions.values():
        if session.shared_id and session.activity_id and session.activity_id in day_vars:
            shared_groups.setdefault(session.shared_id, []).append(session.activity_id)
    for _shared_id, activity_ids in shared_groups.items():
        unique = sorted({aid for aid in activity_ids if aid in data.activities})
        if len(unique) < 2:
            continue
        root = unique[0]
        root_act = data.activities[root]
        root_slots = set(slots_for_duration(root_act.duration_min, root_act.turn))
        for other in unique[1:]:
            other_act = data.activities[other]
            other_slots = set(slots_for_duration(other_act.duration_min, other_act.turn))
            if not root_slots.intersection(other_slots):
                continue  # inconsistent torn on shared teaching event — skip hard link
            model.Add(day_vars[other] == day_vars[root])
            model.Add(start_vars[other] == start_vars[root])

    soft_terms: list[cp_model.LinearExprT] = []

    # Soft: stay close to partida day/time (canvis_franja proxy)
    for activity in activities:
        if activity.id in pinned_ids:
            continue
        template = session_template(data, activity)
        changed_day = model.NewBoolVar(f"chg_day_{activity.id}")
        model.Add(day_vars[activity.id] != day_index(template.day)).OnlyEnforceIf(changed_day)
        model.Add(day_vars[activity.id] == day_index(template.day)).OnlyEnforceIf(changed_day.Not())
        soft_terms.append(changed_day * WEIGHT_CANVI_DIA)

        # |start - partida| / 30 as integer steps
        delta = model.NewIntVar(0, 24 * 2, f"dstart_{activity.id}")
        model.AddAbsEquality(delta, start_vars[activity.id] - template.start_min)
        soft_terms.append(delta * WEIGHT_CANVI_HORA)

    # Pairwise no-overlap only when activities share an ISO week (calendar-faithful)
    for i, left in enumerate(activities):
        for right in activities[i + 1 :]:
            if same_teaching_event(left, right, data):
                continue  # linked by id_compartida — equality constraints handle them
            share_teacher = bool(left.teachers & right.teachers)
            share_cohort = bool(set(left.cohorts) & set(right.cohorts)) and cohort_clash(left, right, data)
            plab_block = plab_blocks(left, right)
            if not (share_teacher or share_cohort or plab_block):
                continue
            if not activities_share_iso_week(data, left.id, right.id):
                continue

            same_day = model.NewBoolVar(f"same_day_{left.id}_{right.id}")
            model.Add(day_vars[left.id] == day_vars[right.id]).OnlyEnforceIf(same_day)
            model.Add(day_vars[left.id] != day_vars[right.id]).OnlyEnforceIf(same_day.Not())
            left_end = start_vars[left.id] + left.duration_min
            right_end = start_vars[right.id] + right.duration_min
            left_before = model.NewBoolVar(f"lb_{left.id}_{right.id}")
            right_before = model.NewBoolVar(f"rb_{left.id}_{right.id}")
            model.Add(left_end <= start_vars[right.id]).OnlyEnforceIf([same_day, left_before])
            model.Add(right_end <= start_vars[left.id]).OnlyEnforceIf([same_day, right_before])
            model.AddBoolOr([same_day.Not(), left_before, right_before])

            # Soft hores mortes: gap minutes when same day, same turn, consecutive
            if share_cohort and left.turn == right.turn and left.turn in ("mati", "tarda"):
                gap = model.NewIntVar(0, MATI[1], f"gap_{left.id}_{right.id}")
                model.Add(gap == 0).OnlyEnforceIf(same_day.Not())
                # left then right
                model.Add(gap >= start_vars[right.id] - left_end).OnlyEnforceIf([same_day, left_before])
                model.Add(gap <= start_vars[right.id] - left_end).OnlyEnforceIf([same_day, left_before])
                # right then left
                model.Add(gap >= start_vars[left.id] - right_end).OnlyEnforceIf([same_day, right_before])
                model.Add(gap <= start_vars[left.id] - right_end).OnlyEnforceIf([same_day, right_before])
                soft_terms.append(gap * WEIGHT_HORES_MORTES)

    if soft_terms and not stop_after_first_feasible:
        model.Minimize(sum(soft_terms))

    _apply_phase1_hints(model, day_vars, start_vars, hints)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_s)
    solver.parameters.num_search_workers = 8
    solver.parameters.stop_after_first_solution = bool(stop_after_first_feasible)
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        activity_day = {a.id: day_from_index(solver.Value(day_vars[a.id])) for a in activities}
        activity_start = {a.id: solver.Value(start_vars[a.id]) for a in activities}
        use_obj = bool(soft_terms) and not stop_after_first_feasible
        objective = int(solver.ObjectiveValue()) if use_obj else 0
        return Phase1Result(True, activity_day, activity_start, status_name, "phase1 ok", objective=objective)
    if status == cp_model.INFEASIBLE:
        return Phase1Result(False, {}, {}, "INFEASIBLE", "phase1 failed")
    return Phase1Result(
        False,
        {},
        {},
        "UNKNOWN",
        "phase1 timeout (UNKNOWN, not infeasible)",
    )


def expand_phase1_to_assignments(
    data: TimetableData,
    phase1: Phase1Result,
) -> list[Assignment]:
    """Temporary assignments with partida rooms (filled in phase 2)."""
    out: list[Assignment] = []
    for session in data.sessions.values():
        if session.activity_id and session.activity_id in phase1.activity_day:
            day = phase1.activity_day[session.activity_id]
            start = phase1.activity_start[session.activity_id]
        else:
            day = session.day
            start = session.start_min
        out.append(
            Assignment(
                session_id=session.id,
                day=day,
                start_min=start,
                room=(
                    session.room_partida
                    if session.fixed.startswith("R7") and day == session.day and start == session.start_min
                    else ""
                ),
            )
        )
    return out
