"""Independent re-check of the hard Phase 1 rules (D1-D7) on a day/time map.

Pure Python (no ortools): used after every greedy candidate and as a defence after CP-SAT.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

from horaris_solver.domain.models import Activity, TimetableData
from horaris_solver.solver.calendar_rules import activities_share_iso_week, overlaps
from horaris_solver.solver.conflicts import activities_interact, session_template
from horaris_solver.solver.feasibility import allowed_days, allowed_starts, domain_values, is_pinned
from horaris_solver.solver.inherited import is_inherited_pair, partida_overlap_pairs
from horaris_solver.solver.rules import Phase1Rules, pool_violations, sibling_violations
from horaris_solver.solver.slots import day_index, slots_for_duration
from horaris_solver.solver.violations import Violation

if TYPE_CHECKING:  # phase1_time imports ortools; the validator must stay pure Python at runtime.
    from horaris_solver.solver.phase1_time import Phase1Result

_DAYS = frozenset({"L", "M", "X", "J", "V"})

Placement = tuple[int, int]


def _placements(data: TimetableData, result: Phase1Result) -> tuple[dict[str, Placement], list[Violation]]:
    """(day_idx, start) per known activity, plus MISSING for activities without a valid day or start."""
    placed: dict[str, Placement] = {}
    missing: list[Violation] = []
    for aid in sorted(data.activities):
        day = result.activity_day.get(aid)
        start = result.activity_start.get(aid)
        if day is None or start is None:
            missing.append(Violation("MISSING", (aid,), "no day or start in result"))
        elif day not in _DAYS:
            missing.append(Violation("MISSING", (aid,), f"unknown day {day!r}"))
        else:
            placed[aid] = (day_index(day), start)
    return placed, missing


def _domain_violations(data: TimetableData, placed: Mapping[str, Placement]) -> Iterator[Violation]:
    """D3 for pinned activities; D1 (turn window) or D2 (calendar) for movable ones."""
    for aid, (day_idx, start) in placed.items():
        activity = data.activities[aid]
        if is_pinned(activity):
            template = session_template(data, activity)
            expected = (day_index(template.day), template.start_min)
            if (day_idx, start) != expected:
                yield Violation("D3-PINNED", (aid,), f"moved from partida {expected} to {(day_idx, start)}")
        elif start not in slots_for_duration(activity.duration_min, activity.turn):
            yield Violation("D1-TURN", (aid,), f"start {start} outside turn {activity.turn}")
        elif day_idx not in allowed_days(data, activity) or start not in allowed_starts(data, activity, day_idx):
            yield Violation("D2-CALENDAR", (aid,), f"day {day_idx} start {start} hits the calendar")


def _clash_violations(data: TimetableData, placed: Mapping[str, Placement]) -> Iterator[Violation]:
    """D4 by weekday bucket and start-sorted sweep; pinned-pinned and partida-overlapping pairs are inherited."""
    inherited = partida_overlap_pairs(data)
    buckets: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for aid, (day_idx, start) in placed.items():
        buckets[day_idx].append((start, aid))
    for entries in buckets.values():
        entries.sort()
        for i, (start, aid) in enumerate(entries):
            left = data.activities[aid]
            for other_start, other in entries[i + 1 :]:
                right = data.activities[other]
                if not overlaps(start, left.duration_min, other_start, right.duration_min):
                    break  # sorted by start: no later entry can overlap this one
                if is_pinned(left) and is_pinned(right):
                    continue
                if is_inherited_pair(inherited, aid, other):
                    continue
                if activities_interact(left, right, data) and activities_share_iso_week(data, aid, other):
                    pair = tuple(sorted((aid, other)))
                    yield Violation("D4-CLASH", pair, f"overlap on day {placed[aid][0]}")


def _shared_groups(data: TimetableData) -> list[list[str]]:
    """Sorted activity ids per id_compartida (groups of 2+ known activities)."""
    groups: dict[str, set[str]] = defaultdict(set)
    for session in data.sessions.values():
        if session.shared_id and session.activity_id in data.activities:
            groups[session.shared_id].add(session.activity_id)
    return [sorted(ids) for _, ids in sorted(groups.items()) if len(ids) >= 2]


def shared_domain(data: TimetableData, activity: Activity) -> frozenset[Placement]:
    """Values a shared member may take in Phase 1: its partida slot when pinned, else its legal domain."""
    if is_pinned(activity):
        template = session_template(data, activity)
        return frozenset({(day_index(template.day), template.start_min)})
    return frozenset(domain_values(data, activity))


def shared_link_pairs(
    group: list[str], domains: Mapping[str, frozenset[Placement]], fixed_ids: set[str]
) -> tuple[list[tuple[str, str]], list[str]]:
    """(root, other) links exactly as phase1_time.shared_links builds them, plus the members left unlinked.

    The first fixed member (else the first member) is the root; two fixed members are never linked; a member
    whose domain misses the running intersection stays unlinked.
    """
    root = next((aid for aid in group if aid in fixed_ids), group[0])
    common = domains[root]
    links: list[tuple[str, str]] = []
    unlinked: list[str] = []
    for other in group:
        if other == root or (other in fixed_ids and root in fixed_ids):
            continue
        overlap = common & domains[other]
        if not overlap:
            unlinked.append(other)
            continue
        links.append((root, other))
        common = overlap
    return links, unlinked


def _shared_violations(data: TimetableData, placed: Mapping[str, Placement]) -> Iterator[Violation]:
    """D5 for each (root, member) link phase1_time.shared_links would add whose two slots differ."""
    for group in _shared_groups(data):
        domains = {aid: shared_domain(data, data.activities[aid]) for aid in group}
        fixed_ids = {aid for aid in group if is_pinned(data.activities[aid])}
        links, _ = shared_link_pairs(group, domains, fixed_ids)
        for root, other in links:
            if root not in placed or other not in placed or placed[root] == placed[other]:
                continue
            left, right = sorted((root, other))
            yield Violation("D5-SHARED", (left, right), f"{placed[left]} != {placed[right]}")


def _rule_violations(
    data: TimetableData, result: Phase1Result, placed: Mapping[str, Placement], rules: Phase1Rules
) -> Iterator[Violation]:
    """D6 / D7 delegated to rules.py, restricted to validly placed activities."""
    activity_day = {aid: result.activity_day[aid] for aid in placed}
    if rules.room_pools:
        activity_start = {aid: start for aid, (_, start) in placed.items()}
        yield from pool_violations(data, activity_day, activity_start)
    if rules.same_kind_day:
        yield from sibling_violations(data, activity_day)


def validate_phase1(data: TimetableData, result: Phase1Result, rules: Phase1Rules | None = None) -> list[Violation]:
    """All hard-rule violations of a Phase 1 result, sorted by (rule, activity_ids)."""
    placed, violations = _placements(data, result)
    violations.extend(_domain_violations(data, placed))
    violations.extend(_clash_violations(data, placed))
    violations.extend(_shared_violations(data, placed))
    if rules is not None:
        violations.extend(_rule_violations(data, result, placed, rules))
    return sorted(violations, key=lambda v: (v.rule, v.activity_ids))
