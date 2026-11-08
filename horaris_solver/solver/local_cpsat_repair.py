"""Local CP-SAT repair for a small set of unplaced activities + neighbors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from horaris_solver.domain.models import TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.slots import day_from_index, day_index, slots_for_duration

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
    """Unplaced ids plus every activity that currently clashes with them.

    Size caps may drop only non-blocking extras, never current clashers.
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
    max_time_s: int = 30,
) -> tuple[dict[str, str], dict[str, int], int] | None:
    """Free neighbors of ``unplaced`` and re-solve that subgraph with CP-SAT.

    Returns updated day/start maps and extra moves, or None if still infeasible
    or timed out (see LAST_STATUS). UNKNOWN is not labelled INFEASIBLE.
    """
    global LAST_STATUS
    LAST_STATUS = None
    if not unplaced:
        LAST_STATUS = "OK"
        return activity_day, activity_start, 0

    free_ids = blocking_neighborhood(data, placed=placed, unplaced=unplaced)

    model = cp_model.CpModel()
    day_vars: dict[str, cp_model.IntVar] = {}
    start_vars: dict[str, cp_model.IntVar] = {}

    for aid, (day_idx, start) in placed.items():
        if aid in free_ids:
            continue
        day_vars[aid] = model.NewConstant(day_idx)
        start_vars[aid] = model.NewConstant(start)

    for aid in free_ids:
        activity = data.activities[aid]
        slots = slots_for_duration(activity.duration_min, activity.turn)
        if not slots:
            LAST_STATUS = "INFEASIBLE"
            return None
        day_vars[aid] = model.NewIntVar(0, 4, f"d_{aid}")
        start_vars[aid] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(slots), f"s_{aid}")

    shared: dict[str, list[str]] = {}
    for session in data.sessions.values():
        if session.shared_id and session.activity_id in day_vars:
            shared.setdefault(session.shared_id, []).append(session.activity_id)
    for aids in shared.values():
        unique = sorted(set(aids))
        if len(unique) < 2:
            continue
        root_id = unique[0]
        for peer_id in unique[1:]:
            model.Add(day_vars[peer_id] == day_vars[root_id])
            model.Add(start_vars[peer_id] == start_vars[root_id])

    free_list = sorted(free_ids)
    all_ids = list(day_vars)
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
            same = model.NewBoolVar(f"same_{left_id}_{right_id}")
            model.Add(day_vars[left_id] == day_vars[right_id]).OnlyEnforceIf(same)
            model.Add(day_vars[left_id] != day_vars[right_id]).OnlyEnforceIf(same.Not())
            left_before = model.NewBoolVar(f"lb_{left_id}_{right_id}")
            right_before = model.NewBoolVar(f"rb_{left_id}_{right_id}")
            model.Add(start_vars[left_id] + left.duration_min <= start_vars[right_id]).OnlyEnforceIf(
                [same, left_before]
            )
            model.Add(start_vars[right_id] + right.duration_min <= start_vars[left_id]).OnlyEnforceIf(
                [same, right_before]
            )
            model.AddBoolOr([same.Not(), left_before, right_before])

    soft: list[cp_model.LinearExprT] = []
    for aid in free_list:
        template = session_template(data, data.activities[aid])
        chg = model.NewBoolVar(f"chg_{aid}")
        model.Add(day_vars[aid] != day_index(template.day)).OnlyEnforceIf(chg)
        model.Add(day_vars[aid] == day_index(template.day)).OnlyEnforceIf(chg.Not())
        soft.append(chg)
        delta = model.NewIntVar(0, 24 * 2, f"ds_{aid}")
        model.AddAbsEquality(delta, start_vars[aid] - template.start_min)
        soft.append(delta)
    if soft:
        model.Minimize(sum(soft))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_time_s)
    solver.parameters.num_search_workers = 1
    solver.parameters.stop_after_first_solution = True
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
        placed[aid] = (day_idx, start)

    return new_day, new_start, moved_extra
