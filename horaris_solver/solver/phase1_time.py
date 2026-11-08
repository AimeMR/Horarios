"""Phase 1: assign day + start time per activity (CP-SAT)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from horaris_solver.domain.models import MATI, Assignment, TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week, week_monday
from horaris_solver.solver.conflicts import (
    cohort_clash,
    plab_blocks,
    same_teaching_event,
    session_template,
)
from horaris_solver.solver.feasibility import domain_values, is_pinned
from horaris_solver.solver.inherited import is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.rules import (
    Phase1Rules,
    activity_pools,
    fixed_pool_intervals,
    pool_capacity,
    sibling_pairs,
)
from horaris_solver.solver.slots import day_from_index, day_index
from horaris_solver.solver.soft_weights import (
    WEIGHT_CANVI_DIA,
    WEIGHT_CANVI_HORA,
    WEIGHT_HORES_MORTES,
    WEIGHT_SOLAPAMENT_HERETAT,
    WEIGHT_SOLAPAMENT_RELAXAT,
)

MINUTES_PER_DAY = 24 * 60
STEP_MIN = 30
WEEK_MINUTES = 7 * MINUTES_PER_DAY


@dataclass(frozen=True)
class Phase1Result:
    ok: bool
    activity_day: dict[str, str]
    activity_start: dict[str, int]
    status: str
    message: str
    objective: int = 0
    unplaced: tuple[str, ...] = ()


def shared_groups(data: TimetableData, activity_ids: Iterable[str]) -> list[list[str]]:
    """Sorted activity ids per id_compartida, restricted to ``activity_ids`` (groups of 2+ only)."""
    wanted = set(activity_ids)
    groups: dict[str, set[str]] = {}
    for session in data.sessions.values():
        if session.shared_id and session.activity_id in wanted:
            groups.setdefault(session.shared_id, set()).add(session.activity_id)
    return [sorted(ids) for ids in groups.values() if len(ids) >= 2]


def shared_links(
    group: list[str],
    domains: Mapping[str, frozenset[tuple[int, int]]],
    fixed_ids: set[str],
) -> list[tuple[str, str]]:
    """(root, other) equality links for one id_compartida group.

    A fixed member (constant) becomes the root so the others follow it. Members whose domain does not
    intersect the running intersection stay unlinked (inconsistent data); two fixed members are never linked.
    """
    root = next((aid for aid in group if aid in fixed_ids), group[0])
    common = domains[root]
    links: list[tuple[str, str]] = []
    for other in group:
        if other == root or (other in fixed_ids and root in fixed_ids):
            continue
        overlap = common & domains[other]
        if not overlap:
            continue
        links.append((root, other))
        common = overlap
    return links


def add_domain_vars(
    model: cp_model.CpModel,
    activity_id: str,
    values: tuple[tuple[int, int], ...],
    *,
    day_prefix: str,
    start_prefix: str,
) -> tuple[cp_model.IntVar, cp_model.IntVar]:
    """Day/start IntVars restricted to the exact (day, start) pairs from feasibility.domain_values."""
    days = sorted({day for day, _ in values})
    starts = sorted({start for _, start in values})
    day_var = model.NewIntVarFromDomain(cp_model.Domain.FromValues(days), f"{day_prefix}{activity_id}")
    start_var = model.NewIntVarFromDomain(cp_model.Domain.FromValues(starts), f"{start_prefix}{activity_id}")
    model.AddAllowedAssignments([day_var, start_var], [list(pair) for pair in values])
    return day_var, start_var


def add_partida_cost(
    model: cp_model.CpModel,
    activity_id: str,
    partida: tuple[int, int],
    day_var: cp_model.IntVar,
    start_var: cp_model.IntVar,
    *,
    sessions: int = 1,
) -> list[cp_model.LinearExprT]:
    """Soft canvi de franja: WEIGHT_CANVI_DIA if the day changes plus WEIGHT_CANVI_HORA per 30-minute step.

    ``sessions`` scales both terms (B1: the verifier counts moved sessions, not activities).
    """
    partida_day, partida_start = partida
    changed_day = model.NewBoolVar(f"chg_day_{activity_id}")
    model.Add(day_var != partida_day).OnlyEnforceIf(changed_day)
    model.Add(day_var == partida_day).OnlyEnforceIf(changed_day.Not())
    delta = model.NewIntVar(0, MINUTES_PER_DAY, f"dstart_{activity_id}")
    model.AddAbsEquality(delta, start_var - partida_start)
    steps = model.NewIntVar(0, MINUTES_PER_DAY // STEP_MIN, f"dsteps_{activity_id}")
    model.AddDivisionEquality(steps, delta, STEP_MIN)
    return [changed_day * (WEIGHT_CANVI_DIA * sessions), steps * (WEIGHT_CANVI_HORA * sessions)]


@dataclass(frozen=True)
class PairSeparation:
    """Literals of one pairwise no-overlap: same weekday, left-before-right, right-before-left."""

    same_day: cp_model.IntVar
    left_before: cp_model.IntVar
    right_before: cp_model.IntVar


def add_pair_separation(
    model: cp_model.CpModel,
    pair: tuple[tuple[str, int], tuple[str, int]],
    day_vars: Mapping[str, cp_model.IntVar],
    start_vars: Mapping[str, cp_model.IntVar],
    *,
    overlap_weight: int | None = None,
    soft_terms: list[cp_model.LinearExprT] | None = None,
) -> PairSeparation:
    """No-overlap of ((left_id, left_dur), (right_id, right_dur)) on the same weekday.

    ``overlap_weight=None`` makes it hard; otherwise the overlap minutes go to ``soft_terms`` at that weight.
    """
    (left_id, left_dur), (right_id, right_dur) = pair
    same_day = model.NewBoolVar(f"same_day_{left_id}_{right_id}")
    model.Add(day_vars[left_id] == day_vars[right_id]).OnlyEnforceIf(same_day)
    model.Add(day_vars[left_id] != day_vars[right_id]).OnlyEnforceIf(same_day.Not())
    left_end = start_vars[left_id] + left_dur
    right_end = start_vars[right_id] + right_dur
    left_before = model.NewBoolVar(f"lb_{left_id}_{right_id}")
    right_before = model.NewBoolVar(f"rb_{left_id}_{right_id}")
    model.Add(left_end <= start_vars[right_id]).OnlyEnforceIf([same_day, left_before])
    model.Add(right_end <= start_vars[left_id]).OnlyEnforceIf([same_day, right_before])
    if overlap_weight is None:
        model.AddBoolOr([same_day.Not(), left_before, right_before])
        return PairSeparation(same_day, left_before, right_before)
    earliest_end = model.NewIntVar(0, 2 * MINUTES_PER_DAY, f"emin_{left_id}_{right_id}")
    latest_start = model.NewIntVar(0, 2 * MINUTES_PER_DAY, f"smax_{left_id}_{right_id}")
    model.AddMinEquality(earliest_end, [left_end, right_end])
    model.AddMaxEquality(latest_start, [start_vars[left_id], start_vars[right_id]])
    overlap = model.NewIntVar(0, min(left_dur, right_dur), f"ov_{left_id}_{right_id}")
    model.Add(overlap >= earliest_end - latest_start).OnlyEnforceIf(same_day)
    if soft_terms is not None:
        soft_terms.append(overlap * overlap_weight)
    return PairSeparation(same_day, left_before, right_before)


def overlap_weight(inherited: bool, soft_overlap: bool) -> int | None:
    """Inherited partida overlaps are always soft; others only in the last-resort soft_overlap mode."""
    if inherited:
        return WEIGHT_SOLAPAMENT_HERETAT
    return WEIGHT_SOLAPAMENT_RELAXAT if soft_overlap else None


def _count_overlaps(
    data: TimetableData,
    pairs: list[tuple[str, str]],
    activity_day: Mapping[str, str],
    activity_start: Mapping[str, int],
) -> int:
    count = 0
    for left_id, right_id in pairs:
        if activity_day[left_id] != activity_day[right_id]:
            continue
        left_start, right_start = activity_start[left_id], activity_start[right_id]
        left_dur, right_dur = data.activities[left_id].duration_min, data.activities[right_id].duration_min
        if left_start < right_start + right_dur and right_start < left_start + left_dur:
            count += 1
    return count


def _grid_size(duration: int) -> int:
    """Duration rounded up to whole 30-minute slots (the D6 validator counts touched slots)."""
    return -(-duration // STEP_MIN) * STEP_MIN


def _grid_interval(start: int, duration: int) -> tuple[int, int]:
    """(start, size) of [start, start + duration) widened to the 30-minute grid anchored at 08:30."""
    origin = MATI[0]
    first = origin + ((start - origin) // STEP_MIN) * STEP_MIN
    last = origin - ((origin - start - duration) // STEP_MIN) * STEP_MIN
    return first, last - first


def _slot_levels(intervals: list[tuple[int, int, int]]) -> dict[int, int]:
    """Summed demand per 30-minute grid slot start of grid-aligned (start, size, demand) intervals."""
    levels: dict[int, int] = defaultdict(int)
    for start, size, demand in intervals:
        for slot in range(start, start + size, STEP_MIN):
            levels[slot] += demand
    return levels


def _clipped_profile(levels: Mapping[int, int], cap: int) -> list[tuple[int, int, int]]:
    """(start, size, demand) runs of the per-slot demand clipped to ``cap`` (same as rules._fixed_counts)."""
    runs: list[tuple[int, int, int]] = []
    for slot in sorted(levels):
        demand = min(levels[slot], cap)
        if demand <= 0:
            continue
        if runs and runs[-1][0] + runs[-1][1] == slot and runs[-1][2] == demand:
            runs[-1] = (runs[-1][0], runs[-1][1] + STEP_MIN, demand)
        else:
            runs.append((slot, STEP_MIN, demand))
    return runs


def _fixed_grid_intervals(
    fixed: Mapping[tuple[date, str], list[tuple[int, int, int]]], key: tuple[date, str]
) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for t_abs, duration, demand in fixed.get(key, []):
        day_offset, start = divmod(t_abs, MINUTES_PER_DAY)
        grid_start, size = _grid_interval(start, duration)
        out.append((day_offset * MINUTES_PER_DAY + grid_start, size, demand))
    return out


def _add_sibling_days(model: cp_model.CpModel, data: TimetableData, day_vars: Mapping[str, cp_model.IntVar]) -> None:
    """D7: same (group, code, kind) siblings sharing an ISO week take different weekdays."""
    for left, right in sibling_pairs(data):
        model.Add(day_vars[left] != day_vars[right])


def _add_room_pools(
    model: cp_model.CpModel,
    data: TimetableData,
    day_vars: Mapping[str, cp_model.IntVar],
    start_vars: Mapping[str, cp_model.IntVar],
    pinned_ids: set[str],
) -> list[str]:
    """D6: one AddCumulative per (ISO Monday, pool); returns notes for data-infeasible pools.

    Fixed demand is clipped to the capacity per slot, so the capacity stays real for movable sessions
    everywhere (as in rules.PoolTable and rules.pool_violations).
    """
    movable: dict[tuple[date, str], list[cp_model.IntervalVar]] = defaultdict(list)
    for activity in data.activities.values():
        pools = activity_pools(data, activity)
        if activity.id in pinned_ids or not pools:
            continue
        t_var = model.NewIntVar(0, WEEK_MINUTES, f"t_{activity.id}")
        model.Add(t_var == MINUTES_PER_DAY * day_vars[activity.id] + start_vars[activity.id])
        for sid in activity.session_ids:
            session = data.sessions[sid]
            interval = model.NewFixedSizeIntervalVar(t_var, _grid_size(session.duration_min), f"pool_{sid}")
            for pool in sorted(pools):
                movable[(week_monday(session.session_date), pool)].append(interval)

    capacity = pool_capacity(data)
    fixed = fixed_pool_intervals(data)
    notes: list[str] = []
    for key in sorted(movable):
        monday, pool = key
        cap = capacity[pool]
        levels = _slot_levels(_fixed_grid_intervals(fixed, key))
        peak = max(levels.values(), default=0)
        if peak > cap:
            notes.append(
                f"D6 fixed occupancy exceeds pool {pool} capacity in week {monday.isoformat()} by {peak - cap}"
            )
        fixed_grid = _clipped_profile(levels, cap)
        fixed_vars = [
            model.NewFixedSizeIntervalVar(start, size, f"fixed_{pool}_{monday.isoformat()}_{i}")
            for i, (start, size, _) in enumerate(fixed_grid)
        ]
        demands = [1] * len(movable[key]) + [demand for _, _, demand in fixed_grid]
        model.AddCumulative(movable[key] + fixed_vars, demands, cap)
    return notes


def _with_notes(message: str, notes: list[str]) -> str:
    return "; ".join([message, *notes])


def _apply_phase1_hints(
    model: cp_model.CpModel,
    day_vars: dict[str, cp_model.IntVar],
    start_vars: dict[str, cp_model.IntVar],
    hints: Phase1Result | None,
    pinned_ids: set[str],
) -> None:
    if hints is None:
        return
    for activity_id, day in hints.activity_day.items():
        day_var = day_vars.get(activity_id)
        if day_var is None or activity_id in pinned_ids:
            continue
        model.add_hint(day_var, day_index(day))
    for activity_id, start in hints.activity_start.items():
        start_var = start_vars.get(activity_id)
        if start_var is None or activity_id in pinned_ids:
            continue
        model.add_hint(start_var, start)


def solve_phase1(
    data: TimetableData,
    *,
    max_time_s: float = 150,
    hints: Phase1Result | None = None,
    stop_after_first_feasible: bool = False,
    random_seed: int | None = None,
    num_workers: int = 8,
    rules: Phase1Rules | None = None,
    deterministic: bool = False,
    soft_overlap: bool = False,
) -> Phase1Result:
    """CP-SAT day/start per activity; ``rules`` adds D6/D7 and B1 session scaling, ``rules=None`` keeps hybrid.

    ``deterministic`` uses one worker and a deterministic-time limit; wall time stays capped at ``max_time_s``.
    Pairs already overlapping in partida (inherited) are never hard: their overlap is only penalised.
    ``soft_overlap`` is the last resort: every other pairwise no-overlap becomes a heavy penalty and the
    status is ``RELAXED_R4`` when some overlap remains.
    """
    model = cp_model.CpModel()
    activities = list(data.activities.values())

    day_vars: dict[str, cp_model.IntVar] = {}
    start_vars: dict[str, cp_model.IntVar] = {}
    domains: dict[str, frozenset[tuple[int, int]]] = {}
    pinned_ids = {a.id for a in activities if is_pinned(a)}
    soft_terms: list[cp_model.LinearExprT] = []

    for activity in activities:
        template = session_template(data, activity)
        partida = (day_index(template.day), template.start_min)
        if activity.id in pinned_ids:
            # R1-FIXADA / R7-PLAB: constants at partida, whatever the turn.
            day_vars[activity.id] = model.NewConstant(partida[0])
            start_vars[activity.id] = model.NewConstant(partida[1])
            domains[activity.id] = frozenset({partida})
            continue
        values = domain_values(data, activity)
        if not values:
            return Phase1Result(False, {}, {}, "INFEASIBLE_DATA", f"empty domain for activity {activity.id}")
        domains[activity.id] = frozenset(values)
        day_vars[activity.id], start_vars[activity.id] = add_domain_vars(
            model, activity.id, values, day_prefix="day_", start_prefix="start_"
        )
        sessions = len(activity.session_ids) if rules is not None else 1
        soft_terms.extend(
            add_partida_cost(
                model, activity.id, partida, day_vars[activity.id], start_vars[activity.id], sessions=sessions
            )
        )

    # Shared sessions (same id_compartida) must share day+time when domains allow it (R4-COMPARTIDA).
    for group in shared_groups(data, day_vars):
        for root, other in shared_links(group, domains, pinned_ids):
            model.Add(day_vars[other] == day_vars[root])
            model.Add(start_vars[other] == start_vars[root])

    # Pairwise no-overlap only when activities share an ISO week (calendar-faithful).
    # Pinned-pinned clashes are inherited from partida (the verifier marks them heretada): no constraint.
    # Other pairs already overlapping in partida are inherited too: soft penalty instead of a hard constraint.
    inherited = partida_overlap_pairs(data)
    relaxed_pairs: list[tuple[str, str]] = []
    for i, left in enumerate(activities):
        for right in activities[i + 1 :]:
            if left.id in pinned_ids and right.id in pinned_ids:
                continue
            if same_teaching_event(left, right, data):
                continue  # linked by id_compartida — equality constraints handle them
            share_teacher = bool(left.teachers & right.teachers)
            share_cohort = bool(set(left.cohorts) & set(right.cohorts)) and cohort_clash(left, right, data)
            plab_block = plab_blocks(left, right)
            if not (share_teacher or share_cohort or plab_block):
                continue
            if not activities_share_iso_week(data, left.id, right.id):
                continue

            is_inherited = is_inherited_pair(inherited, left.id, right.id)
            if soft_overlap and not is_inherited:
                relaxed_pairs.append((left.id, right.id))
            separation = add_pair_separation(
                model,
                ((left.id, left.duration_min), (right.id, right.duration_min)),
                day_vars,
                start_vars,
                overlap_weight=overlap_weight(is_inherited, soft_overlap),
                soft_terms=soft_terms,
            )
            same_day, left_before, right_before = separation.same_day, separation.left_before, separation.right_before
            left_end = start_vars[left.id] + left.duration_min
            right_end = start_vars[right.id] + right.duration_min

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

    notes: list[str] = []
    if rules is not None and rules.same_kind_day:
        _add_sibling_days(model, data, day_vars)
    if rules is not None and rules.room_pools:
        notes = _add_room_pools(model, data, day_vars, start_vars, pinned_ids)

    if soft_terms and not stop_after_first_feasible:
        model.Minimize(sum(soft_terms))

    _apply_phase1_hints(model, day_vars, start_vars, hints, pinned_ids)

    solver = cp_model.CpSolver()
    if deterministic:
        solver.parameters.max_deterministic_time = float(max_time_s)
        solver.parameters.max_time_in_seconds = float(max_time_s)
        solver.parameters.num_search_workers = 1
    else:
        solver.parameters.max_time_in_seconds = float(max_time_s)
        solver.parameters.num_search_workers = num_workers
    solver.parameters.stop_after_first_solution = bool(stop_after_first_feasible)
    if random_seed is not None:
        solver.parameters.random_seed = random_seed
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        activity_day = {a.id: day_from_index(solver.Value(day_vars[a.id])) for a in activities}
        activity_start = {a.id: solver.Value(start_vars[a.id]) for a in activities}
        use_obj = bool(soft_terms) and not stop_after_first_feasible
        objective = int(solver.ObjectiveValue()) if use_obj else 0
        overlapping = _count_overlaps(data, relaxed_pairs, activity_day, activity_start)
        if overlapping:
            message = _with_notes(f"phase1 relaxed R4: {overlapping} overlapping pairs", notes)
            return Phase1Result(True, activity_day, activity_start, "RELAXED_R4", message, objective=objective)
        message = _with_notes("phase1 ok", notes)
        return Phase1Result(True, activity_day, activity_start, status_name, message, objective=objective)
    if status == cp_model.INFEASIBLE:
        return Phase1Result(False, {}, {}, "INFEASIBLE", _with_notes("phase1 failed", notes))
    return Phase1Result(
        False,
        {},
        {},
        "UNKNOWN",
        _with_notes("phase1 timeout (UNKNOWN, not infeasible)", notes),
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
