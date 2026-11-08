"""Greedy day/time repair from partida — feasible non-overlapping schedule.

Without seed or rules it is the deterministic greedy used by ``hybrid``. With ``rules`` it also honours
the team rules (D6 pool capacity, D7 siblings on distinct days); with ``seed`` it becomes one GRASP
construction (randomised restricted candidate list and perturbed slot preference, plan §5.1-5.2).
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from horaris_solver.domain.models import Activity, TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week, overlaps
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.feasibility import domain_values, is_pinned
from horaris_solver.solver.inherited import is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.local_cpsat_repair import repair_unplaced_with_cpsat
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.rules import (
    Phase1Rules,
    PoolTable,
    activity_pools,
    pool_capacity,
    pool_violations,
    sibling_day_conflicts,
    sibling_pairs,
    sibling_violations,
)
from horaris_solver.solver.slots import day_from_index, day_index

_MAX_BLOCKERS = 8
_KIND_RANK = {"TE": 0, "PAUL": 1, "SEM": 2, "PLAB": 3}
_WEIGHT_DAY = 200.0
_WEIGHT_STEP = 2.0
_WEIGHT_GAP = 10.0
_STEP_MIN = 30

_Slot = tuple[int, int]


@dataclass(frozen=True)
class GreedyPerturbation:
    """GRASP knobs: RCL size (alpha, max), slot-weight jitter and how many cheapest slots to sample from."""

    rcl_alpha: float = 0.15
    rcl_max: int = 8
    weight_jitter: float = 0.2
    top_slots: int = 3

    def __post_init__(self) -> None:
        if not 0 < self.rcl_alpha <= 1:
            raise ValueError("rcl_alpha must be in (0, 1]")
        if self.rcl_max < 1:
            raise ValueError("rcl_max must be >= 1")
        if not 0 <= self.weight_jitter < 1:
            raise ValueError("weight_jitter must be in [0, 1)")
        if self.top_slots < 1:
            raise ValueError("top_slots must be >= 1")


@dataclass(frozen=True)
class _SlotWeights:
    day: float
    step: float
    gap: float


@dataclass
class _Chooser:
    """Seeded randomness of one GRASP run; never touches the global random module."""

    rng: random.Random
    perturbation: GreedyPerturbation
    weights: _SlotWeights

    @classmethod
    def build(cls, seed: int, perturbation: GreedyPerturbation) -> _Chooser:
        rng = random.Random(seed)  # noqa: S311  # nosec B311 — reproducible search diversity, not security
        low, high = 1 - perturbation.weight_jitter, 1 + perturbation.weight_jitter
        weights = _SlotWeights(
            day=_WEIGHT_DAY * rng.uniform(low, high),
            step=_WEIGHT_STEP * rng.uniform(low, high),
            gap=_WEIGHT_GAP * rng.uniform(low, high),
        )
        return cls(rng=rng, perturbation=perturbation, weights=weights)

    def rcl_pick(self, remaining: int) -> int:
        """Index into the ordered remaining list, uniform over the restricted candidate list."""
        size = min(self.perturbation.rcl_max, math.ceil(self.perturbation.rcl_alpha * remaining))
        return self.rng.randrange(max(1, min(size, remaining)))

    def slot_pick(self, ranked: list[_Slot]) -> _Slot:
        top = ranked[: self.perturbation.top_slots]
        return top[self.rng.randrange(len(top))]


def _ordered_domain(data: TimetableData, activity: Activity) -> list[_Slot]:
    """Legal (day_idx, start) pairs from feasibility, partida first, then by distance to partida."""
    template = session_template(data, activity)
    partida_day = day_index(template.day)

    def cost(value: _Slot) -> tuple[int, int, int]:
        day_idx, start = value
        return (abs(start - template.start_min) + 1000 * abs(day_idx - partida_day), day_idx, start)

    return sorted(domain_values(data, activity), key=cost)


def _shared_groups(data: TimetableData) -> dict[str, tuple[str, ...]]:
    """activity id -> every activity linked to it through id_compartida (transitively), itself included."""
    by_shared: dict[str, set[str]] = {}
    for session in data.sessions.values():
        if session.shared_id and session.activity_id in data.activities:
            by_shared.setdefault(session.shared_id, set()).add(session.activity_id)
    links: dict[str, set[str]] = {aid: set() for aid in data.activities}
    for members in by_shared.values():
        for aid in members:
            links[aid] |= members
    groups: dict[str, tuple[str, ...]] = {}
    for aid in data.activities:
        if aid in groups:
            continue
        seen = {aid}
        stack = [aid]
        while stack:
            for other in links[stack.pop()]:
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        group = tuple(sorted(seen))
        for member in group:
            groups[member] = group
    return groups


def _pairs_index(data: TimetableData) -> dict[str, tuple[str, ...]]:
    """activity id -> its D7 siblings (sorted)."""
    index: dict[str, list[str]] = defaultdict(list)
    for left, right in sibling_pairs(data):
        index[left].append(right)
        index[right].append(left)
    return {aid: tuple(sorted(others)) for aid, others in index.items()}


def _clashes_placed(
    activity: Activity,
    day_idx: int,
    start: int,
    placed: dict[str, _Slot],
    data: TimetableData,
    *,
    ignore: frozenset[str] = frozenset(),
    inherited: frozenset[tuple[str, str]] = frozenset(),
) -> list[str]:
    """Placed activities that clash with activity at (day_idx, start).

    Pinned-pinned pairs and pairs already overlapping in partida (``inherited``) are exempt.
    """
    pinned = is_pinned(activity)
    hits: list[str] = []
    for other_id, (other_day, other_start) in placed.items():
        if other_id in ignore or other_day != day_idx:
            continue
        other = data.activities[other_id]
        if pinned and is_pinned(other):
            continue
        if is_inherited_pair(inherited, activity.id, other_id):
            continue
        if not activities_interact(activity, other, data):
            continue
        if not activities_share_iso_week(data, activity.id, other_id):
            continue
        if overlaps(start, activity.duration_min, other_start, other.duration_min):
            hits.append(other_id)
    return hits


@dataclass
class _GreedyState:
    data: TimetableData
    groups: dict[str, tuple[str, ...]]
    domains: dict[str, list[_Slot]]
    pools: PoolTable | None = None
    pairs_index: dict[str, tuple[str, ...]] | None = None
    chooser: _Chooser | None = None
    inherited: frozenset[tuple[str, str]] = frozenset()
    activity_day: dict[str, str] = field(default_factory=dict)
    activity_start: dict[str, int] = field(default_factory=dict)
    placed: dict[str, _Slot] = field(default_factory=dict)
    cohort_day: dict[tuple[str, int], dict[str, _Slot]] = field(default_factory=dict)
    moved: int = 0

    # --- occupancy bookkeeping (maps, pool table, cohort index) ---------------------------------

    def occupy(self, member: str, day_idx: int, start: int) -> None:
        self.activity_day[member] = day_from_index(day_idx)
        self.activity_start[member] = start
        self.placed[member] = (day_idx, start)
        activity = self.data.activities[member]
        if self.pools is not None:
            self.pools.add(activity, day_idx, start)
        if self.chooser is not None:
            for cohort in activity.cohorts:
                self.cohort_day.setdefault((cohort, day_idx), {})[member] = (start, start + activity.duration_min)

    def vacate(self, member: str) -> None:
        slot = self.placed.pop(member, None)
        self.activity_day.pop(member, None)
        self.activity_start.pop(member, None)
        if slot is None:
            return
        activity = self.data.activities[member]
        if self.pools is not None:
            self.pools.remove(activity, *slot)
        if self.chooser is not None:
            for cohort in activity.cohorts:
                self.cohort_day.get((cohort, slot[0]), {}).pop(member, None)

    def snapshot(self) -> tuple[dict[str, _Slot], int]:
        return dict(self.placed), self.moved

    def restore(self, snap: tuple[dict[str, _Slot], int]) -> None:
        target, moved = snap
        for member in sorted(m for m, slot in self.placed.items() if target.get(m) != slot):
            self.vacate(member)
        for member in sorted(m for m in target if m not in self.placed):
            self.occupy(member, *target[member])
        self.moved = moved

    # --- candidate filters ----------------------------------------------------------------------

    def group_candidates(self, activity: Activity) -> list[_Slot]:
        """Slots legal for every member of the shared group, ordered by the activity's own cost."""
        group = self.groups[activity.id]
        common = set(self.domains[activity.id])
        for member in group:
            common &= set(self.domains[member])
        return [value for value in self.domains[activity.id] if value in common]

    def group_blockers(self, activity: Activity, day_idx: int, start: int, *, strict: bool = False) -> list[str]:
        """Union of clashes of every unplaced group member at (day_idx, start).

        ``strict`` also counts pairs inherited from partida, so their overlap is avoided when possible.
        """
        inherited = frozenset() if strict else self.inherited
        group = self.groups[activity.id]
        ignore = frozenset(group)
        hits: list[str] = []
        for member in group:
            if member in self.placed:
                continue
            for hit in _clashes_placed(
                self.data.activities[member],
                day_idx,
                start,
                self.placed,
                self.data,
                ignore=ignore,
                inherited=inherited,
            ):
                if hit not in hits:
                    hits.append(hit)
        return hits

    def _unplaced_members(self, activity: Activity) -> list[str]:
        return [m for m in self.groups[activity.id] if m not in self.placed]

    def _siblings_ok(self, members: list[str], day_idx: int) -> bool:
        if self.pairs_index is None:
            return True
        pending = set(members)
        for member in members:
            if sibling_day_conflicts(self.data, self.pairs_index, member, day_idx, self.activity_day):
                return False
            if any(other in pending for other in self.pairs_index.get(member, ())):
                return False
        return True

    def _pools_ok(self, members: list[str], day_idx: int, start: int) -> bool:
        if self.pools is None:
            return True
        added: list[Activity] = []
        fits = True
        for member in members:
            activity = self.data.activities[member]
            if not self.pools.fits(activity, day_idx, start):
                fits = False
                break
            self.pools.add(activity, day_idx, start)
            added.append(activity)
        for activity in added:
            self.pools.remove(activity, day_idx, start)
        return fits

    def rules_ok(self, activity: Activity, day_idx: int, start: int) -> bool:
        members = self._unplaced_members(activity)
        return self._siblings_ok(members, day_idx) and self._pools_ok(members, day_idx, start)

    def feasible(self, activity: Activity, day_idx: int, start: int, *, strict: bool = False) -> bool:
        return not self.group_blockers(activity, day_idx, start, strict=strict) and self.rules_ok(
            activity, day_idx, start
        )

    # --- slot preference (seeded runs) ----------------------------------------------------------

    def _gap_estimate(self, activity: Activity, day_idx: int, start: int) -> int:
        """Minutes between the new block and the nearest class of each cohort that day (cheap proxy)."""
        end = start + activity.duration_min
        group = set(self.groups[activity.id])
        total = 0
        for cohort in activity.cohorts:
            others = [iv for aid, iv in self.cohort_day.get((cohort, day_idx), {}).items() if aid not in group]
            if others:
                total += min(max(0, other_start - end, start - other_end) for other_start, other_end in others)
        return total

    def _slot_cost(self, chooser: _Chooser, activity: Activity, day_idx: int, start: int) -> float:
        template = session_template(self.data, activity)
        weights = chooser.weights
        day_changed = 1 if day_idx != day_index(template.day) else 0
        steps = abs(start - template.start_min) // _STEP_MIN
        sessions = len(activity.session_ids)
        gap = self._gap_estimate(activity, day_idx, start)
        return sessions * (weights.day * day_changed + weights.step * steps) + weights.gap * gap

    def choose_slot(self, activity: Activity) -> _Slot | None:
        """Best slot avoiding every overlap; only if none exists, one that keeps an inherited partida overlap."""
        candidates = self.group_candidates(activity)
        slot = self._choose_among(activity, candidates, strict=True)
        if slot is None and self.inherited:
            slot = self._choose_among(activity, candidates, strict=False)
        return slot

    def _choose_among(self, activity: Activity, candidates: list[_Slot], *, strict: bool) -> _Slot | None:
        chooser = self.chooser
        if chooser is None:
            return next((slot for slot in candidates if self.feasible(activity, *slot, strict=strict)), None)
        ranked = sorted(
            (slot for slot in candidates if self.feasible(activity, *slot, strict=strict)),
            key=lambda slot: (self._slot_cost(chooser, activity, *slot), slot),
        )
        return chooser.slot_pick(ranked) if ranked else None

    # --- moves ----------------------------------------------------------------------------------

    def place_group(self, activity: Activity, day_idx: int, start: int, *, count_move: bool) -> None:
        """Place every unplaced member of the group; call only after the slot is feasible."""
        for member in self.groups[activity.id]:
            if member not in self.placed:
                self.occupy(member, day_idx, start)
        if not count_move or is_pinned(activity):
            return
        template = session_template(self.data, activity)
        if day_idx != day_index(template.day) or start != template.start_min:
            self.moved += 1

    def unplace_group(self, activity_id: str) -> None:
        for member in self.groups[activity_id]:
            self.vacate(member)

    def try_place(self, activity: Activity) -> bool:
        slot = self.choose_slot(activity)
        if slot is None:
            return False
        self.place_group(activity, *slot, count_move=True)
        return True

    def try_displace(self, activity: Activity) -> bool:
        for day_idx, start in self.group_candidates(activity):
            blockers = self.group_blockers(activity, day_idx, start)
            if len(blockers) > _MAX_BLOCKERS:
                continue
            blocker_groups = sorted({self.groups[b][0] for b in blockers})
            members = {m for leader in blocker_groups for m in self.groups[leader]}
            if any(is_pinned(self.data.activities[m]) for m in members):
                continue
            snap = self.snapshot()
            for leader in blocker_groups:
                self.unplace_group(leader)
            if not self.feasible(activity, day_idx, start):
                self.restore(snap)
                continue
            self.place_group(activity, day_idx, start, count_move=True)
            if all(self.try_place(self.data.activities[leader]) for leader in blocker_groups):
                return True
            self.restore(snap)
        return False


def _legacy_order(state: _GreedyState, activities: list[Activity]) -> list[Activity]:
    def key(activity: Activity) -> tuple[int, int, int, int, str]:
        # Longest first (3h labs) so they take the few morning windows that fit.
        return (
            -activity.duration_min,
            _KIND_RANK.get(activity.kind, 9),
            -activity.students,
            len(state.domains[activity.id]),
            activity.id,
        )

    return sorted(activities, key=key)


def _pinned_neighbours(data: TimetableData, activities: list[Activity]) -> dict[str, int]:
    """Number of pinned activities each movable activity interacts with (same ISO week)."""
    by_key: dict[str, list[Activity]] = defaultdict(list)
    for pinned in (a for a in activities if is_pinned(a)):
        keys = {f"t:{t}" for t in pinned.teachers} | {f"c:{c}" for c in pinned.cohorts} | {f"k:{pinned.code}"}
        for key in keys:
            by_key[key].append(pinned)
    counts: dict[str, int] = {}
    for activity in activities:
        keys = {f"t:{t}" for t in activity.teachers} | {f"c:{c}" for c in activity.cohorts} | {f"k:{activity.code}"}
        near = {p.id: p for key in keys for p in by_key.get(key, ())}
        counts[activity.id] = sum(
            1
            for pid, pinned in near.items()
            if pid != activity.id
            and activities_interact(activity, pinned, data)
            and activities_share_iso_week(data, activity.id, pid)
        )
    return counts


def _pool_pressure(data: TimetableData, activities: list[Activity], enabled: bool) -> dict[str, float]:
    """Max demand/capacity ratio over the pools each activity uses (0 when pools are off)."""
    if not enabled:
        return {a.id: 0.0 for a in activities}
    capacity = pool_capacity(data)
    demand: dict[str, int] = defaultdict(int)
    pools_of = {a.id: activity_pools(data, a) for a in activities}
    for activity in activities:
        if is_pinned(activity):
            continue
        for pool in pools_of[activity.id]:
            demand[pool] += len(activity.session_ids) * activity.duration_min
    ratio = {pool: (demand[pool] / capacity[pool] if capacity[pool] else math.inf) for pool in demand}
    return {a.id: max((ratio[p] for p in pools_of[a.id] if p in ratio), default=0.0) for a in activities}


def _constrained_order(state: _GreedyState, activities: list[Activity], pools_on: bool) -> list[Activity]:
    """Most-constrained-first order (plan §5.1)."""
    feasible = {a.id: len(state.group_candidates(a)) for a in activities}
    neighbours = _pinned_neighbours(state.data, activities)
    pressure = _pool_pressure(state.data, activities, pools_on)

    def key(activity: Activity) -> tuple[int, int, float, int, int, int, str]:
        return (
            feasible[activity.id],
            -neighbours[activity.id],
            -pressure[activity.id],
            -len(state.groups[activity.id]),
            -activity.duration_min,
            -activity.students,
            activity.id,
        )

    return sorted(activities, key=key)


def _construct(state: _GreedyState, ordered: list[Activity]) -> list[str]:
    """Place activities in order (RCL-sampled when seeded); return those that found no slot."""
    remaining = [a for a in ordered if a.id not in state.placed]
    unplaced: list[str] = []
    while remaining:
        index = state.chooser.rcl_pick(len(remaining)) if state.chooser is not None else 0
        activity = remaining.pop(index)
        if activity.id in state.placed:
            continue
        if not state.try_place(activity):
            unplaced.append(activity.id)
    return unplaced


def _breaks_rules(data: TimetableData, rules: Phase1Rules, day: dict[str, str], start: dict[str, int]) -> bool:
    if rules.same_kind_day and sibling_violations(data, day):
        return True
    return rules.room_pools and bool(pool_violations(data, day, start))


def solve_phase1_greedy(
    data: TimetableData,
    *,
    seed: int | None = None,
    rules: Phase1Rules | None = None,
    perturbation: GreedyPerturbation | None = None,
    repair_time_s: float = 45.0,
    deterministic: bool = False,
) -> Phase1Result:
    """Build a conflict-free day/time map by repairing partida greedily.

    ``perturbation`` only takes effect together with ``seed`` (defaults to ``GreedyPerturbation()``).
    ``seed`` and ``deterministic`` are forwarded to the CP-SAT repair of leftover activities.
    """
    activities = list(data.activities.values())
    domains = {a.id: _ordered_domain(data, a) for a in activities}
    chooser = _Chooser.build(seed, perturbation or GreedyPerturbation()) if seed is not None else None
    state = _GreedyState(
        data=data,
        groups=_shared_groups(data),
        domains=domains,
        pools=PoolTable(data) if rules is not None and rules.room_pools else None,
        pairs_index=_pairs_index(data) if rules is not None and rules.same_kind_day else None,
        chooser=chooser,
        inherited=partida_overlap_pairs(data),
    )

    for activity in activities:
        if is_pinned(activity):
            template = session_template(data, activity)
            state.occupy(activity.id, day_index(template.day), template.start_min)

    if rules is None and chooser is None:
        ordered = _legacy_order(state, activities)
    else:
        ordered = _constrained_order(state, activities, pools_on=state.pools is not None)
    unplaced = _construct(state, ordered)

    still: list[str] = []
    for aid in unplaced:
        if aid in state.placed:
            continue
        if state.try_displace(data.activities[aid]):
            continue
        still.append(aid)

    activity_day = state.activity_day
    activity_start = state.activity_start
    moved = state.moved
    if still:
        repaired = repair_unplaced_with_cpsat(
            data,
            placed=state.placed,
            activity_day=activity_day,
            activity_start=activity_start,
            unplaced=still,
            max_time_s=repair_time_s,
            random_seed=seed,
            deterministic=deterministic,
        )
        # The CP-SAT repair does not know the team rules: drop its answer if it breaks them.
        if repaired is not None and not (rules is not None and _breaks_rules(data, rules, repaired[0], repaired[1])):
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
        return Phase1Result(False, {}, {}, "INFEASIBLE", f"greedy missing activities {missing[:5]}")

    return Phase1Result(
        True,
        activity_day,
        activity_start,
        "GREEDY",
        f"greedy ok moved≈{moved}",
        objective=moved,
    )
