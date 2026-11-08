"""Data precheck before Phase 1: blocking issues mean INFEASIBLE_DATA, warnings are inherited from the partida.

Messages carry only activity ids, counts, dates and pool names (never teachers, codes or groups).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from horaris_solver.domain.models import MATI, TARDA, Activity, Session, TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.feasibility import allowed_days, domain_values, is_pinned
from horaris_solver.solver.inherited import ActivityPair, is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.rules import Phase1Rules, fixed_pool_intervals, pool_capacity, sibling_groups
from horaris_solver.solver.slots import day_from_index, day_index, start_fits_turn
from horaris_solver.solver.validate import shared_domain, shared_link_pairs

_Domain = frozenset[tuple[int, int]]


@dataclass(frozen=True)
class PrecheckIssue:
    code: str
    activity_ids: tuple[str, ...]
    message: str
    blocking: bool


@dataclass(frozen=True)
class PrecheckReport:
    issues: tuple[PrecheckIssue, ...]

    @property
    def blocking(self) -> bool:
        return any(issue.blocking for issue in self.issues)


def _scheduled(data: TimetableData) -> list[Activity]:
    """Activities with at least one loaded session, sorted by id."""
    return sorted(
        (a for a in data.activities.values() if a.session_ids and all(s in data.sessions for s in a.session_ids)),
        key=lambda a: a.id,
    )


def _check_heterogeneous(data: TimetableData, activities: list[Activity]) -> Iterator[PrecheckIssue]:
    for activity in activities:
        shapes = {
            (s.day, s.start_min, s.duration_min, s.fixed) for s in (data.sessions[sid] for sid in activity.session_ids)
        }
        if len(shapes) > 1:
            yield PrecheckIssue(
                "HETEROGENEOUS_ACTIVITY",
                (activity.id,),
                f"activity {activity.id}: sessions differ in weekday/start/duration/fixed ({len(shapes)} variants)",
                blocking=True,
            )


def _check_empty_domain(activities: list[Activity], domains: dict[str, _Domain]) -> Iterator[PrecheckIssue]:
    for activity in activities:
        if not is_pinned(activity) and not domains[activity.id]:
            yield PrecheckIssue(
                "EMPTY_DOMAIN",
                (activity.id,),
                f"activity {activity.id}: no legal (day, start) after turn, calendar and aturades",
                blocking=True,
            )


def _shared_groups(data: TimetableData, activities: list[Activity]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for activity in activities:
        for sid in activity.session_ids:
            shared = data.sessions[sid].shared_id
            if shared:
                groups[shared].add(activity.id)
    return groups


def _check_shared(
    data: TimetableData, activities: list[Activity], domains: dict[str, _Domain]
) -> Iterator[PrecheckIssue]:
    """Blocking when phase1_time.shared_links would leave a member unlinked (pinned-pinned pairs are exempt)."""
    for members in _shared_groups(data, activities).values():
        if len(members) < 2:
            continue
        group = sorted(members)
        fixed_ids = {aid for aid in group if is_pinned(data.activities[aid])}
        if not all(domains[aid] for aid in group if aid not in fixed_ids):
            continue  # already reported as EMPTY_DOMAIN
        group_domains = {aid: shared_domain(data, data.activities[aid]) for aid in group}
        _, unlinked = shared_link_pairs(group, group_domains, fixed_ids)
        if unlinked:
            root = next((aid for aid in group if aid in fixed_ids), group[0])
            ids = tuple(sorted({root, *unlinked}))
            yield PrecheckIssue(
                "SHARED_NO_COMMON_SLOT",
                ids,
                f"shared group of {len(ids)} activities has no common (day, start): {', '.join(ids)}",
                blocking=True,
            )


def _check_pinned_turn(data: TimetableData, activities: list[Activity]) -> Iterator[PrecheckIssue]:
    for activity in activities:
        if not is_pinned(activity):
            continue
        template = session_template(data, activity)
        if not start_fits_turn(template.start_min, template.duration_min, activity.turn):
            yield PrecheckIssue(
                "PINNED_OUT_OF_TURN",
                (activity.id,),
                f"pinned activity {activity.id}: partida start is outside its turn (kept fixed)",
                blocking=False,
            )


def _pinned_sessions_by_date(data: TimetableData, activities: list[Activity]) -> dict[date, list[Session]]:
    by_date: dict[date, list[Session]] = defaultdict(list)
    for activity in activities:
        if is_pinned(activity):
            for sid in activity.session_ids:
                session = data.sessions[sid]
                by_date[session.session_date].append(session)
    return by_date


def _overlapping_pairs(sessions: list[Session]) -> Iterator[tuple[str, str]]:
    """Activity id pairs (a < b) whose sessions overlap in time; sweep over start-sorted sessions."""
    active: list[Session] = []
    for session in sorted(sessions, key=lambda s: (s.start_min, s.id)):
        active = [other for other in active if other.end_min > session.start_min]
        for other in active:
            if other.activity_id != session.activity_id:
                left, right = sorted((other.activity_id, session.activity_id))
                yield left, right
        active.append(session)


def _check_pinned_clash(data: TimetableData, activities: list[Activity]) -> Iterator[PrecheckIssue]:
    pairs: set[tuple[str, str]] = set()
    for sessions in _pinned_sessions_by_date(data, activities).values():
        pairs.update(_overlapping_pairs(sessions))
    for left, right in sorted(pairs):
        if activities_interact(data.activities[left], data.activities[right], data):
            yield PrecheckIssue(
                "PINNED_CLASH",
                (left, right),
                f"pinned activities {left} and {right} already clash in the partida (tolerated)",
                blocking=False,
            )


def _shared_units(data: TimetableData, ids: tuple[str, ...]) -> list[set[str]]:
    """Partition ids into units linked by a common id_compartida (they must share day and time)."""
    parent = {aid: aid for aid in ids}

    def find(aid: str) -> str:
        while parent[aid] != aid:
            parent[aid] = parent[parent[aid]]
            aid = parent[aid]
        return aid

    owner: dict[str, str] = {}
    for aid in ids:
        for sid in data.activities[aid].session_ids:
            shared = data.sessions[sid].shared_id
            if not shared:
                continue
            if shared in owner:
                parent[find(aid)] = find(owner[shared])
            else:
                owner[shared] = aid
    units: dict[str, set[str]] = defaultdict(set)
    for aid in ids:
        units[find(aid)].add(aid)
    return list(units.values())


def _check_siblings(data: TimetableData, scheduled: set[str]) -> Iterator[PrecheckIssue]:
    for group in sibling_groups(data):
        ids = tuple(aid for aid in group.activity_ids if aid in scheduled)
        pinned_days: set[int] = set()
        movable_units: list[set[str]] = []
        for unit in _shared_units(data, ids):
            pinned = [data.activities[aid] for aid in unit if is_pinned(data.activities[aid])]
            if pinned:
                pinned_days.update(day_index(session_template(data, a).day) for a in pinned)
            else:
                movable_units.append(unit)
        available = {d for unit in movable_units for aid in unit for d in allowed_days(data, data.activities[aid])}
        available -= pinned_days
        if len(movable_units) > len(available):
            members = tuple(sorted(aid for unit in movable_units for aid in unit))
            yield PrecheckIssue(
                "SIBLINGS_EXCEED_DAYS",
                members,
                f"{len(movable_units)} sibling units need distinct days in week {group.key[3].isoformat()} "
                f"but only {len(available)} days are available: {', '.join(members)}",
                blocking=True,
            )


def _peak(intervals: list[tuple[int, int, int]]) -> int:
    """Maximum simultaneous demand over half-open intervals (t, duration, demand); ends sort before starts."""
    events = sorted(e for t, dur, demand in intervals for e in ((t, demand), (t + dur, -demand)))
    current = best = 0
    for _, delta in events:
        current += delta
        best = max(best, current)
    return best


def _check_pools(data: TimetableData) -> Iterator[PrecheckIssue]:
    capacity = pool_capacity(data)
    for (monday, pool), intervals in sorted(fixed_pool_intervals(data).items()):
        peak = _peak(intervals)
        if peak > capacity[pool]:
            yield PrecheckIssue(
                "POOL_OVER_CAPACITY",
                (),
                f"pool {pool} week {monday.isoformat()}: {peak} fixed sessions at once > capacity {capacity[pool]}",
                blocking=False,
            )


_TURN_WINDOWS: dict[str, tuple[tuple[int, int], ...]] = {"mati": (MATI,), "tarda": (TARDA,)}


def _turn_windows(turn: str) -> tuple[tuple[int, int], ...]:
    """Windows a movable activity of this turn may use; an unknown turn ("?") may use either."""
    return _TURN_WINDOWS.get(turn, (MATI, TARDA))


def _single_legal_day(data: TimetableData, activity: Activity, domains: dict[str, _Domain]) -> int | None:
    """The only weekday the activity can take (days with a legal start), or None if it has 0 or 2+."""
    days = set(allowed_days(data, activity)) if is_pinned(activity) else {d for d, _ in domains[activity.id]}
    return next(iter(days)) if len(days) == 1 else None


def _week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _single_day_groups(
    data: TimetableData, activities: list[Activity], domains: dict[str, _Domain]
) -> dict[tuple[date, int, str], list[Activity]]:
    """Single-day activities grouped by (ISO week Monday, weekday, turn)."""
    groups: dict[tuple[date, int, str], list[Activity]] = defaultdict(list)
    for activity in activities:
        day = _single_legal_day(data, activity, domains)
        if day is None:
            continue
        weeks = {_week_monday(data.sessions[sid].session_date) for sid in activity.session_ids}
        for monday in weeks:
            groups[(monday, day, activity.turn)].append(activity)
    return groups


def _hard_separated(data: TimetableData, inherited: frozenset[ActivityPair], left: Activity, right: Activity) -> bool:
    """True exactly when Phase 1 forbids the pair to overlap (same predicates as phase1_time / greedy / validate)."""
    if is_pinned(left) and is_pinned(right):
        return False  # pinned-pinned clashes are inherited from partida
    if is_inherited_pair(inherited, left.id, right.id):
        return False  # already overlapping in partida: soft penalty only
    return activities_interact(left, right, data) and activities_share_iso_week(data, left.id, right.id)


def _clique_compatible(
    data: TimetableData, inherited: frozenset[ActivityPair], left: Activity, right: Activity
) -> bool:
    """Pinned members are fixed intervals (they may overlap each other); every other pair must be hard-separated."""
    return (is_pinned(left) and is_pinned(right)) or _hard_separated(data, inherited, left, right)


def _greedy_cliques(
    data: TimetableData, members: list[Activity], inherited: frozenset[ActivityPair]
) -> Iterator[list[Activity]]:
    """Partition members into sets whose movable members must avoid each other and every pinned member."""
    pending = sorted(members, key=lambda a: (-a.duration_min, a.id))
    while pending:
        clique = [pending.pop(0)]
        rest: list[Activity] = []
        for candidate in pending:
            if all(_clique_compatible(data, inherited, candidate, other) for other in clique):
                clique.append(candidate)
            else:
                rest.append(candidate)
        pending = rest
        yield clique


def _covered_minutes(intervals: list[tuple[int, int]], window: tuple[int, int]) -> int:
    """Minutes of window covered by the union of half-open intervals (start, end)."""
    clipped = sorted((max(s, window[0]), min(e, window[1])) for s, e in intervals if s < window[1] and e > window[0])
    covered = 0
    cursor = window[0]
    for start, end in clipped:
        start = max(start, cursor)
        if end > start:
            covered += end - start
            cursor = end
    return covered


def _free_minutes(data: TimetableData, clique: list[Activity], turn: str) -> int:
    """Turn-window minutes left once the pinned members' partida intervals are removed."""
    pinned = [session_template(data, a) for a in clique if is_pinned(a)]
    intervals = [(t.start_min, t.start_min + t.duration_min) for t in pinned]
    return sum(end - start - _covered_minutes(intervals, (start, end)) for start, end in _turn_windows(turn))


def _check_single_day_overload(
    data: TimetableData, activities: list[Activity], domains: dict[str, _Domain]
) -> Iterator[PrecheckIssue]:
    """Blocking only when the movable members provably cannot fit: their pairwise-disjoint demand exceeds the free
    turn minutes on their single legal day once pinned members (which they must avoid) are removed."""
    inherited = partida_overlap_pairs(data)
    reported: set[tuple[str, ...]] = set()
    for (monday, day, turn), members in sorted(_single_day_groups(data, activities, domains).items()):
        for clique in _greedy_cliques(data, members, inherited):
            ids = tuple(sorted(a.id for a in clique))
            demand = sum(a.duration_min for a in clique if not is_pinned(a))
            free = _free_minutes(data, clique, turn)
            if len(clique) < 2 or demand <= free or ids in reported:
                continue
            reported.add(ids)
            yield PrecheckIssue(
                "SINGLE_DAY_OVERLOAD",
                ids,
                f"activities {', '.join(ids)} week {monday.isoformat()} weekday {day_from_index(day)}: "
                f"demand {demand} min > window {free} min (single legal weekday due to calendar closures)",
                blocking=True,
            )


def run_precheck(data: TimetableData, rules: Phase1Rules | None = None) -> PrecheckReport:
    """Check data consistency before solving; rule-dependent checks run only when rules enable them."""
    activities = _scheduled(data)
    domains = {a.id: frozenset(domain_values(data, a)) for a in activities}
    issues = [
        *_check_heterogeneous(data, activities),
        *_check_empty_domain(activities, domains),
        *_check_shared(data, activities, domains),
        *_check_pinned_turn(data, activities),
        *_check_pinned_clash(data, activities),
        *_check_single_day_overload(data, activities, domains),
    ]
    if rules is not None and rules.same_kind_day:
        issues.extend(_check_siblings(data, {a.id for a in activities}))
    if rules is not None and rules.room_pools:
        issues.extend(_check_pools(data))
    return PrecheckReport(tuple(issues))
