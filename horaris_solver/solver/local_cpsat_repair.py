"""Local CP-SAT repair for a small set of unplaced activities + neighbors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from horaris_solver.domain.models import TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.feasibility import domain_values, is_pinned
from horaris_solver.solver.inherited import is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.phase1_time import (
    add_domain_vars,
    add_pair_separation,
    add_partida_cost,
    overlap_weight,
    shared_groups,
    shared_links,
)
from horaris_solver.solver.slots import day_from_index, day_index

if TYPE_CHECKING:
    from ortools.sat.python import cp_model as cp_model
else:
    from ortools.sat.python import cp_model as _ortools_cp_model

    class _IsolatedCpSolver(_ortools_cp_model.CpSolver):
        """Own class so tests can patch this module without hooking global OR-Tools."""

    class _CpModelProxy:
        """Re-export OR-Tools with a local CpSolver the tests can monkeypatch safely."""

        CpModel = _ortools_cp_model.CpModel
        CpSolver = _IsolatedCpSolver
        Domain = _ortools_cp_model.Domain
        OPTIMAL = _ortools_cp_model.OPTIMAL
        FEASIBLE = _ortools_cp_model.FEASIBLE
        INFEASIBLE = _ortools_cp_model.INFEASIBLE
        UNKNOWN = _ortools_cp_model.UNKNOWN

        def __getattr__(self, name: str) -> object:
            return getattr(_ortools_cp_model, name)

    cp_model = _CpModelProxy()

LAST_STATUS: str | None = None
_NEIGHBORHOOD_CAP = 80


def blocking_neighborhood(
    data: TimetableData,
    *,
    placed: dict[str, tuple[int, int]],
    unplaced: list[str],
) -> set[str]:
    """Unplaced ids plus every movable activity that currently clashes with them.

    Pinned neighbours (R1/R7) are never freed. Size caps may drop only non-blocking extras, never clashers.
    """
    free_ids = set(unplaced)
    clashers: set[str] = set()
    extras: list[str] = []
    unplaced_set = set(unplaced)
    for uid in unplaced:
        seed = data.activities[uid]
        for neighbor_id in placed:
            if neighbor_id in unplaced_set:
                continue
            neighbor = data.activities[neighbor_id]
            if is_pinned(neighbor):
                continue
            if not activities_interact(seed, neighbor, data):
                extras.append(neighbor_id)
                continue
            if not activities_share_iso_week(data, uid, neighbor_id):
                extras.append(neighbor_id)
                continue
            clashers.add(neighbor_id)
    free_ids |= clashers
    leftover = [aid for aid in extras if aid not in free_ids]
    leftover = list(dict.fromkeys(leftover))
    room = _NEIGHBORHOOD_CAP - len(free_ids)
    if room > 0:
        leftover.sort(key=lambda aid: (data.activities[aid].duration_min, aid))
        free_ids.update(leftover[:room])
    return free_ids


def repair_unplaced_with_cpsat(
    data: TimetableData,
    *,
    placed: dict[str, tuple[int, int]],
    activity_day: dict[str, str],
    activity_start: dict[str, int],
    unplaced: list[str],
    max_time_s: float = 30,
    random_seed: int | None = None,
    deterministic: bool = False,
) -> tuple[dict[str, str], dict[str, int], int] | None:
    """Free neighbors of ``unplaced`` and re-solve that subgraph with CP-SAT.

    Returns new day/start maps and extra moves, or None if still infeasible
    or timed out (see LAST_STATUS). UNKNOWN is not labelled INFEASIBLE.
    The arguments are never mutated. ``deterministic`` uses one worker and a
    deterministic-time limit (wall time still capped at ``max_time_s``).
    """
    global LAST_STATUS
    LAST_STATUS = None
    if not unplaced:
        LAST_STATUS = "OK"
        return dict(activity_day), dict(activity_start), 0

    free_ids = blocking_neighborhood(data, placed=placed, unplaced=unplaced)

    model = cp_model.CpModel()
    day_vars: dict[str, cp_model.IntVar] = {}
    start_vars: dict[str, cp_model.IntVar] = {}
    domains: dict[str, frozenset[tuple[int, int]]] = {}
    fixed_ids: set[str] = set()
    soft: list[cp_model.LinearExprT] = []

    for aid, (day_idx, start) in placed.items():
        if aid in free_ids:
            continue
        day_vars[aid] = model.NewConstant(day_idx)
        start_vars[aid] = model.NewConstant(start)
        domains[aid] = frozenset({(day_idx, start)})
        fixed_ids.add(aid)

    for aid in sorted(free_ids):
        activity = data.activities[aid]
        values = domain_values(data, activity)
        if not values:
            LAST_STATUS = "INFEASIBLE"
            return None
        domains[aid] = frozenset(values)
        if is_pinned(activity):
            fixed_ids.add(aid)
        day_vars[aid], start_vars[aid] = add_domain_vars(model, aid, values, day_prefix="d_", start_prefix="s_")
        template = session_template(data, activity)
        partida = (day_index(template.day), template.start_min)
        soft.extend(add_partida_cost(model, aid, partida, day_vars[aid], start_vars[aid]))

    for group in shared_groups(data, day_vars):
        for root_id, peer_id in shared_links(group, domains, fixed_ids):
            model.Add(day_vars[peer_id] == day_vars[root_id])
            model.Add(start_vars[peer_id] == start_vars[root_id])

    all_ids = list(day_vars)
    inherited = partida_overlap_pairs(data)
    for i, left_id in enumerate(all_ids):
        left = data.activities[left_id]
        for right_id in all_ids[i + 1 :]:
            right = data.activities[right_id]
            if not activities_interact(left, right, data):
                continue
            if not activities_share_iso_week(data, left_id, right_id):
                continue
            if left_id not in free_ids and right_id not in free_ids:
                continue
            if is_pinned(left) and is_pinned(right):
                continue  # clash inherited from partida (verifier: heretada)
            # Pairs already overlapping in partida are inherited (verifier: heretada): soft, never hard.
            add_pair_separation(
                model,
                ((left_id, left.duration_min), (right_id, right.duration_min)),
                day_vars,
                start_vars,
                overlap_weight=overlap_weight(is_inherited_pair(inherited, left_id, right_id), False),
                soft_terms=soft,
            )

    if soft:
        model.Minimize(sum(soft))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_s)
    if deterministic:
        solver.parameters.max_deterministic_time = float(max_time_s)
        solver.parameters.num_search_workers = 1
    else:
        solver.parameters.num_search_workers = 8
    if random_seed is not None:
        solver.parameters.random_seed = random_seed
    status = solver.Solve(model)
    status_code = int(status)
    if status_code == int(cp_model.UNKNOWN):
        LAST_STATUS = "UNKNOWN"
        return None
    if status_code not in (int(cp_model.OPTIMAL), int(cp_model.FEASIBLE)):
        LAST_STATUS = "INFEASIBLE"
        return None
    LAST_STATUS = "OPTIMAL" if status_code == int(cp_model.OPTIMAL) else "FEASIBLE"

    new_day = dict(activity_day)
    new_start = dict(activity_start)
    moved_extra = 0
    for aid in free_ids:
        day_idx = solver.Value(day_vars[aid])
        start = solver.Value(start_vars[aid])
        template = session_template(data, data.activities[aid])
        if day_idx != day_index(template.day) or start != template.start_min:
            moved_extra += 1
        new_day[aid] = day_from_index(day_idx)
        new_start[aid] = start

    return new_day, new_start, moved_extra
