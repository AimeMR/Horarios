"""Team rules for Phase 1: room-pool capacity (D6) and same-kind siblings on distinct days (D7).

Pure Python, shared by the greedy (PoolTable, sibling_day_conflicts), CP-SAT (fixed_pool_intervals,
sibling_pairs) and the validator (pool_violations, sibling_violations).

Besides the coarse pools G and GX, a movable activity whose first session has a small candidate room
set (1..SMALL_CLASS_MAX rooms, e.g. a PAUL limited to two computer rooms) also consumes an exact
"room-class" pool ``C:<room>|<room>...`` with capacity = number of rooms (no R8 reserve), so phase 1
never moves it to a time when all its candidate rooms are taken by pinned sessions.
"""

from __future__ import annotations

import weakref
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from itertools import combinations

from horaris_solver.domain.models import MATI, Activity, Session, TimetableData, fmt
from horaris_solver.solver.calendar_rules import remap_date_index, week_monday
from horaris_solver.solver.feasibility import is_pinned
from horaris_solver.solver.room_rules import AULA_GENERAL, RESERVA_MIN, room_candidates, unit_students
from horaris_solver.solver.slots import day_from_index, day_index
from horaris_solver.solver.violations import Violation

POOL_GENERAL = "G"
POOL_EXTENDED = "GX"
_POOLS = (POOL_GENERAL, POOL_EXTENDED)
CLASS_POOL_PREFIX = "C:"
SMALL_CLASS_MAX = 6
_SLOT_MIN = 30
_SLOT_ORIGIN = MATI[0]
_DAY_MIN = 1440
_INFORMATICA = "Aules informàtiques"
_EXCLUDED_PREFIX = "J/"

_PoolKey = tuple[date, int, str]


@dataclass(frozen=True)
class Phase1Rules:
    same_kind_day: bool = True
    room_pools: bool = True


@dataclass(frozen=True)
class SiblingGroup:
    key: tuple[str, str, str, date]  # (grup, codi, tipus, ISO Monday)
    activity_ids: tuple[str, ...]


def _pool_rooms(data: TimetableData) -> dict[str, frozenset[str]]:
    general: set[str] = set()
    extended: set[str] = set()
    for room in data.rooms.values():
        if room.code.startswith(_EXCLUDED_PREFIX):
            continue
        if room.kind in AULA_GENERAL:
            general.add(room.code)
            extended.add(room.code)
        elif room.integrated or room.kind == _INFORMATICA:
            extended.add(room.code)
    return {POOL_GENERAL: frozenset(general), POOL_EXTENDED: frozenset(extended)}


def _base_pools(activity: Activity) -> frozenset[str]:
    if activity.sense_espai or activity.kind == "PLAB":
        return frozenset()
    if activity.kind == "PAUL":
        return frozenset({POOL_EXTENDED})
    return frozenset(_POOLS)


@dataclass(frozen=True)
class _ClassIndex:
    by_activity: dict[str, str]  # movable activity id -> class pool id
    rooms: dict[str, frozenset[str]]  # class pool id -> its rooms
    by_room: dict[str, tuple[str, ...]]  # room code -> class pool ids containing it


_CLASS_CACHE: dict[int, _ClassIndex] = {}


def _class_of(
    data: TimetableData, activity: Activity, base: dict[str, frozenset[str]], loads: Mapping[str, int]
) -> frozenset[str] | None:
    """Small candidate room set of a movable activity, or None when it gets no class pool.

    Sets that contain every room of a base pool the activity already consumes are skipped: that base
    pool's constraint is at least as tight.
    """
    pools = _base_pools(activity)
    if is_pinned(activity) or not pools or not activity.session_ids:
        return None
    session = data.sessions[activity.session_ids[0]]
    rooms = frozenset(code for code in room_candidates(data, session, unit_load=loads) if code in data.rooms)
    if not 1 <= len(rooms) <= SMALL_CLASS_MAX:
        return None
    if any(base[pool] and base[pool] <= rooms for pool in pools):
        return None
    return rooms


def _build_class_index(data: TimetableData) -> _ClassIndex:
    base = _pool_rooms(data)
    loads = unit_students(data)
    by_activity: dict[str, str] = {}
    rooms_of: dict[str, frozenset[str]] = {}
    for activity in data.activities.values():
        rooms = _class_of(data, activity, base, loads)
        if rooms is None:
            continue
        pool = CLASS_POOL_PREFIX + "|".join(sorted(rooms))
        by_activity[activity.id] = pool
        rooms_of[pool] = rooms
    by_room: dict[str, list[str]] = defaultdict(list)
    for pool in sorted(rooms_of):
        for code in rooms_of[pool]:
            by_room[code].append(pool)
    return _ClassIndex(by_activity, rooms_of, {code: tuple(pools) for code, pools in by_room.items()})


def _class_index(data: TimetableData) -> _ClassIndex:
    """Class pools of ``data``, computed once per TimetableData object and dropped when it is collected."""
    key = id(data)
    index = _CLASS_CACHE.get(key)
    if index is None:
        index = _build_class_index(data)
        _CLASS_CACHE[key] = index
        weakref.finalize(data, _CLASS_CACHE.pop, key, None)
    return index


def activity_pools(data: TimetableData, activity: Activity) -> frozenset[str]:
    """Pools a mobile activity consumes: TE/SEM -> {G, GX}; PAUL -> {GX}; PLAB or no room -> none.

    A movable activity with a small candidate room set also consumes its room-class pool.
    """
    pools = _base_pools(activity)
    if not pools:
        return pools
    class_pool = _class_index(data).by_activity.get(activity.id)
    return pools | {class_pool} if class_pool else pools


def pool_capacity(data: TimetableData) -> dict[str, int]:
    """Rooms per base pool minus the R8 reserve (never negative); rooms per class pool (no reserve)."""
    capacity = {pool: max(0, len(rooms) - RESERVA_MIN) for pool, rooms in _pool_rooms(data).items()}
    capacity.update({pool: len(rooms) for pool, rooms in _class_index(data).rooms.items()})
    return capacity


def _fixed_sessions(data: TimetableData) -> Iterator[Session]:
    """Sessions that never move: those of pinned activities or with no activity."""
    for session in data.sessions.values():
        activity = data.activities.get(session.activity_id)
        if activity is None or is_pinned(activity):
            yield session


def _fixed_session_pools(data: TimetableData) -> Iterator[tuple[Session, str]]:
    pool_rooms = _pool_rooms(data)
    for session in _fixed_sessions(data):
        for pool in _POOLS:
            if session.room_partida in pool_rooms[pool]:
                yield session, pool


def _merge_spans(spans: list[tuple[int, int]]) -> Iterator[tuple[int, int]]:
    current: tuple[int, int] | None = None
    for start, end in sorted(spans):
        if current is not None and start <= current[1]:
            current = (current[0], max(current[1], end))
            continue
        if current is not None:
            yield current
        current = (start, end)
    if current is not None:
        yield current


def _fixed_class_spans(data: TimetableData) -> Iterator[tuple[str, date, int, int]]:
    """(room, date, start, end) of fixed sessions in class-pool rooms, merged per room and date.

    Sessions sharing a room at the same time (e.g. grouped groups) take that room once.
    """
    class_by_room = _class_index(data).by_room
    spans: dict[tuple[str, date], list[tuple[int, int]]] = defaultdict(list)
    for session in _fixed_sessions(data):
        if session.room_partida in class_by_room:
            spans[(session.room_partida, session.session_date)].append(
                (session.start_min, session.start_min + session.duration_min)
            )
    for (room, session_date), room_spans in sorted(spans.items()):
        for start, end in _merge_spans(room_spans):
            yield room, session_date, start, end


def fixed_pool_intervals(data: TimetableData) -> dict[tuple[date, str], list[tuple[int, int, int]]]:
    """(ISO Monday, pool) -> [(weekday*1440 + start, duration, demand=1)] of fixed sessions in pool rooms.

    For a class pool, each room of the class held by fixed sessions occupies one unit while it is held.
    """
    out: dict[tuple[date, str], list[tuple[int, int, int]]] = defaultdict(list)
    for session, pool in _fixed_session_pools(data):
        t_abs = session.session_date.weekday() * _DAY_MIN + session.start_min
        out[(week_monday(session.session_date), pool)].append((t_abs, session.duration_min, 1))
    class_by_room = _class_index(data).by_room
    for room, session_date, start, end in _fixed_class_spans(data):
        t_abs = session_date.weekday() * _DAY_MIN + start
        for pool in class_by_room[room]:
            out[(week_monday(session_date), pool)].append((t_abs, end - start, 1))
    return dict(out)


def _slots(start: int, duration: int) -> range:
    """30-minute slot indexes (from 08:30) touched by [start, start + duration)."""
    first = (start - _SLOT_ORIGIN) // _SLOT_MIN
    last = -((_SLOT_ORIGIN - start - duration) // _SLOT_MIN)  # ceil((end - origin) / slot)
    return range(first, last)


def _slot_label(slot: int) -> str:
    return fmt(_SLOT_ORIGIN + slot * _SLOT_MIN)


def _session_keys(session_date: date, start: int, duration: int, pools: frozenset[str]) -> Iterator[_PoolKey]:
    for slot in _slots(start, duration):
        for pool in pools:
            yield (session_date, slot, pool)


def _activity_keys(data: TimetableData, activity: Activity, day_idx: int, start: int) -> Iterator[_PoolKey]:
    pools = activity_pools(data, activity)
    if not pools:
        return
    for sid in activity.session_ids:
        session = data.sessions[sid]
        yield from _session_keys(remap_date_index(session.session_date, day_idx), start, session.duration_min, pools)


def _fixed_counts(data: TimetableData) -> dict[_PoolKey, int]:
    """Fixed occupancy per (date, slot, pool), clipped to the pool capacity.

    Fixed sessions alone above capacity are a data issue (precheck reports it); clipping keeps the
    capacity real for movable sessions, exactly as phase 1 CP-SAT models it.
    """
    capacity = pool_capacity(data)
    clipped = {key: min(count, capacity[key[2]]) for key, count in _raw_fixed_counts(data).items()}
    return defaultdict(int, clipped)


def _raw_fixed_counts(data: TimetableData) -> dict[_PoolKey, int]:
    counts: dict[_PoolKey, int] = defaultdict(int)
    for session, pool in _fixed_session_pools(data):
        for key in _session_keys(session.session_date, session.start_min, session.duration_min, frozenset({pool})):
            counts[key] += 1
    class_by_room = _class_index(data).by_room
    held = {
        (session_date, slot, room)
        for room, session_date, start, end in _fixed_class_spans(data)
        for slot in _slots(start, end - start)
    }
    for session_date, slot, room in held:
        for pool in class_by_room[room]:
            counts[(session_date, slot, pool)] += 1
    return dict(counts)


class PoolTable:
    """Mutable (date, slot, pool) occupancy counters for the greedy.

    Fixed sessions are loaded at construction; pinned activities are therefore no-ops for add/remove
    and always fit, so they are never counted twice.
    """

    def __init__(self, data: TimetableData) -> None:
        self._data = data
        self._capacity = pool_capacity(data)
        self._counts = _fixed_counts(data)

    def fits(self, activity: Activity, day_idx: int, start: int) -> bool:
        if is_pinned(activity):
            return True
        return all(
            self._counts.get(key, 0) + 1 <= self._capacity[key[2]]
            for key in _activity_keys(self._data, activity, day_idx, start)
        )

    def add(self, activity: Activity, day_idx: int, start: int) -> None:
        if is_pinned(activity):
            return
        for key in _activity_keys(self._data, activity, day_idx, start):
            self._counts[key] += 1

    def remove(self, activity: Activity, day_idx: int, start: int) -> None:
        if is_pinned(activity):
            return
        keys = list(_activity_keys(self._data, activity, day_idx, start))
        if any(self._counts.get(key, 0) < 1 for key in keys):
            raise ValueError(f"activity {activity.id} is not placed at day {day_idx} start {start}")
        for key in keys:
            self._counts[key] -= 1


def pool_violations(
    data: TimetableData,
    activity_day: Mapping[str, str],
    activity_start: Mapping[str, int],
) -> list[Violation]:
    """D6-POOL per (date, slot, pool) where fixed + mobile demand exceeds capacity.

    Pinned activities are counted as fixed occupancy; unassigned activities are skipped (MISSING is
    reported elsewhere); overflows caused by fixed sessions alone are a data issue, not reported here.
    """
    capacity = pool_capacity(data)
    counts = _fixed_counts(data)
    users: dict[_PoolKey, set[str]] = defaultdict(set)
    for aid, day in activity_day.items():
        activity = data.activities.get(aid)
        if activity is None or is_pinned(activity) or aid not in activity_start:
            continue
        for key in _activity_keys(data, activity, day_index(day), activity_start[aid]):
            counts[key] += 1
            users[key].add(aid)
    violations: list[Violation] = []
    for key in sorted(users):
        session_date, slot, pool = key
        if counts[key] > capacity[pool]:
            detail = (
                f"pool {pool} on {session_date.isoformat()} at {_slot_label(slot)}: "
                f"{counts[key]} sessions > capacity {capacity[pool]}"
            )
            violations.append(Violation("D6-POOL", tuple(sorted(users[key])), detail))
    return violations


def sibling_groups(data: TimetableData) -> tuple[SiblingGroup, ...]:
    """Groups of 2+ activities sharing (group, code, kind) and an ISO week, sorted by key."""
    members: dict[tuple[str, str, str, date], set[str]] = defaultdict(set)
    for activity in data.activities.values():
        if not activity.session_ids:
            continue
        group = data.sessions[activity.session_ids[0]].group
        for sid in activity.session_ids:
            monday = week_monday(data.sessions[sid].session_date)
            members[(group, activity.code, activity.kind, monday)].add(activity.id)
    return tuple(SiblingGroup(key, tuple(sorted(ids))) for key, ids in sorted(members.items()) if len(ids) >= 2)


def _shared_ids(data: TimetableData, activity: Activity) -> set[str]:
    return {data.sessions[sid].shared_id for sid in activity.session_ids if data.sessions[sid].shared_id}


def _exempt_pair(data: TimetableData, left: str, right: str) -> bool:
    a, b = data.activities[left], data.activities[right]
    if is_pinned(a) and is_pinned(b):
        return True
    return bool(_shared_ids(data, a) & _shared_ids(data, b))


def sibling_pairs(data: TimetableData) -> tuple[tuple[str, str], ...]:
    """Sorted (a < b) sibling pairs sharing an ISO week; pinned-pinned and same id_compartida exempt."""
    pairs = {pair for group in sibling_groups(data) for pair in combinations(group.activity_ids, 2)}
    return tuple(sorted(pair for pair in pairs if not _exempt_pair(data, *pair)))


def sibling_day_conflicts(
    data: TimetableData,
    pairs_index: Mapping[str, tuple[str, ...]],
    activity_id: str,
    day_idx: int,
    activity_day: Mapping[str, str],
) -> list[str]:
    """Already-placed siblings of activity_id that sit on weekday day_idx, sorted."""
    day = day_from_index(day_idx)
    return sorted(other for other in pairs_index.get(activity_id, ()) if activity_day.get(other) == day)


def sibling_violations(data: TimetableData, activity_day: Mapping[str, str]) -> list[Violation]:
    """D7-SAME-KIND-DAY for each non-exempt sibling pair placed on the same weekday."""
    return [
        Violation("D7-SAME-KIND-DAY", (a, b), f"both on day {activity_day[a]}")
        for a, b in sibling_pairs(data)
        if a in activity_day and activity_day.get(b) == activity_day[a]
    ]
