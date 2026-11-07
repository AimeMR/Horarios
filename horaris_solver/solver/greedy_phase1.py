"""Greedy day/time repair from partida — feasible non-overlapping schedule."""

from __future__ import annotations

from horaris_solver.domain.models import Activity, TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week, overlaps
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.local_cpsat_repair import repair_unplaced_with_cpsat
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.slots import (
    day_from_index,
    day_index,
    slots_for_duration,
    start_fits_turn,
)


def _candidate_slots(activity: Activity, data: TimetableData) -> list[tuple[int, int]]:
    """(day_idx, start_min) candidates; partida first when valid."""
    template = session_template(data, activity)
    slots = slots_for_duration(activity.duration_min, activity.turn)
    if not slots:
        return []

    ordered: list[tuple[int, int]] = []
    partida = (day_index(template.day), template.start_min)
    scored: list[tuple[int, int, int]] = []
    for day_idx in range(5):
        for start in slots:
            dist = abs(start - template.start_min) + 1000 * abs(
                day_idx - day_index(template.day)
            )
            if (day_idx, start) == partida and start_fits_turn(
                start, activity.duration_min, activity.turn
            ):
                dist = -1
            scored.append((dist, day_idx, start))
    scored.sort()
    for _, day_idx, start in scored:
        ordered.append((day_idx, start))
    return ordered


def _clashes_placed(
    activity: Activity,
    day_idx: int,
    start: int,
    placed: dict[str, tuple[int, int]],
    data: TimetableData,
    *,
    ignore: frozenset[str] = frozenset(),
) -> list[str]:
    hits: list[str] = []
    for other_id, (other_day, other_start) in placed.items():
        if other_id in ignore or other_day != day_idx:
            continue
        other = data.activities[other_id]
        if not activities_interact(activity, other, data):
            continue
        if not activities_share_iso_week(data, activity.id, other_id):
            continue
        if overlaps(start, activity.duration_min, other_start, other.duration_min):
            hits.append(other_id)
    return hits


def _sync_shared(
    activity: Activity,
    day_idx: int,
    start: int,
    *,
    activity_day: dict[str, str],
    activity_start: dict[str, int],
    placed: dict[str, tuple[int, int]],
    data: TimetableData,
) -> None:
    shared_ids = {
        data.sessions[sid].shared_id
        for sid in activity.session_ids
        if data.sessions[sid].shared_id
    }
    if not shared_ids:
        return
    for session in data.sessions.values():
        if session.shared_id not in shared_ids or not session.activity_id:
            continue
        other_id = session.activity_id
        if other_id == activity.id or other_id not in data.activities:
            continue
        activity_day[other_id] = day_from_index(day_idx)
        activity_start[other_id] = start
        placed[other_id] = (day_idx, start)


def solve_phase1_greedy(data: TimetableData) -> Phase1Result:
    """Build a conflict-free day/time map by repairing partida greedily."""
    activities = list(data.activities.values())
    activity_day: dict[str, str] = {}
    activity_start: dict[str, int] = {}
    placed: dict[str, tuple[int, int]] = {}
    moved = 0

    def place(activity: Activity, day_idx: int, start: int, *, count_move: bool) -> None:
        nonlocal moved
        activity_day[activity.id] = day_from_index(day_idx)
        activity_start[activity.id] = start
        placed[activity.id] = (day_idx, start)
        template = session_template(data, activity)
        if count_move and (day_idx != day_index(template.day) or start != template.start_min):
            moved += 1
        _sync_shared(
            activity,
            day_idx,
            start,
            activity_day=activity_day,
            activity_start=activity_start,
            placed=placed,
            data=data,
        )

    def unplace(activity_id: str) -> None:
        placed.pop(activity_id, None)
        activity_day.pop(activity_id, None)
        activity_start.pop(activity_id, None)

    kind_rank = {"TE": 0, "PAUL": 1, "SEM": 2, "PLAB": 3}

    def place_order(activity: Activity) -> tuple[int, int, int, int, str]:
        # Longest first (3h labs) so they take the few morning windows that fit.
        return (
            -activity.duration_min,
            kind_rank.get(activity.kind, 9),
            -activity.students,
            len(_candidate_slots(activity, data)),
            activity.id,
        )

    ordered = sorted(activities, key=place_order)

    unplaced: list[str] = []
    for activity in ordered:
        if activity.id in placed:
            continue
        found = False
        for day_idx, start in _candidate_slots(activity, data):
            if _clashes_placed(activity, day_idx, start, placed, data):
                continue
            place(activity, day_idx, start, count_move=True)
            found = True
            break
        if not found:
            unplaced.append(activity.id)

    def try_displace(activity: Activity) -> bool:
        for day_idx, start in _candidate_slots(activity, data):
            blockers = _clashes_placed(activity, day_idx, start, placed, data)
            if len(blockers) > 8:
                continue
            snapshot = {b: placed[b] for b in blockers}
            for b in blockers:
                unplace(b)
            if _clashes_placed(activity, day_idx, start, placed, data):
                for b, pos in snapshot.items():
                    place(data.activities[b], pos[0], pos[1], count_move=False)
                continue
            place(activity, day_idx, start, count_move=True)
            ok_all = True
            for b in blockers:
                re_placed = False
                for b_day, b_start in _candidate_slots(data.activities[b], data):
                    if _clashes_placed(data.activities[b], b_day, b_start, placed, data):
                        continue
                    place(data.activities[b], b_day, b_start, count_move=True)
                    re_placed = True
                    break
                if not re_placed:
                    ok_all = False
                    break
            if ok_all:
                return True
            unplace(activity.id)
            for b in blockers:
                unplace(b)
            for b, pos in snapshot.items():
                place(data.activities[b], pos[0], pos[1], count_move=False)
        return False

    still: list[str] = []
    for aid in unplaced:
        if aid in placed:
            continue
        if try_displace(data.activities[aid]):
            continue
        still.append(aid)

    if still:
        repaired = repair_unplaced_with_cpsat(
            data,
            placed=placed,
            activity_day=activity_day,
            activity_start=activity_start,
            unplaced=still,
            max_time_s=45,
        )
        if repaired is not None:
            activity_day, activity_start, extra = repaired
            moved += extra
            still = [aid for aid in still if aid not in activity_day]

    if still:
        return Phase1Result(
            False,
            dict(activity_day),
            dict(activity_start),
            "GREEDY_PARTIAL",
            f"greedy could not place {len(still)} activities e.g. {still[:5]}",
            unplaced=tuple(still),
        )

    missing = [a.id for a in activities if a.id not in activity_day]
    if missing:
        return Phase1Result(
            False, {}, {}, "INFEASIBLE", f"greedy missing activities {missing[:5]}"
        )

    return Phase1Result(
        True,
        activity_day,
        activity_start,
        "GREEDY",
        f"greedy ok moved≈{moved}",
        objective=moved,
    )
