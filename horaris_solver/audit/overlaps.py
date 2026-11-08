"""Detect hard room double-bookings (R4-AULA style)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from horaris_solver.domain.models import Assignment, TimetableData, fmt
from horaris_solver.solver.calendar_rules import remap_date


@dataclass(frozen=True)
class RoomOverlap:
    room: str
    on_date: date
    left_id: str
    right_id: str
    left_start: int
    left_end: int
    right_start: int
    right_end: int

    def summary(self) -> str:
        return (
            f"{self.on_date.isoformat()} {self.room}: "
            f"{self.left_id} {fmt(self.left_start)}-{fmt(self.left_end)} × "
            f"{self.right_id} {fmt(self.right_start)}-{fmt(self.right_end)}"
        )


def _time_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def find_room_overlaps(
    data: TimetableData,
    assignments: list[Assignment] | None = None,
    *,
    use_partida: bool = False,
) -> list[RoomOverlap]:
    """Find distinct-unit sessions sharing a room on the same date with overlapping time.

    If ``assignments`` is given, use proposal day/time/room (with dates remapped from
    partida calendar dates). If ``use_partida``, audit the official partida placement.
    """
    if assignments is None and not use_partida:
        raise ValueError("pass assignments=... or use_partida=True")

    by_id: dict[str, Assignment] = {}
    if assignments is not None:
        by_id = {a.session_id: a for a in assignments}

    placed: list[tuple[str, date, int, int, str, str]] = []
    for session in data.sessions.values():
        if session.sense_espai:
            continue
        if use_partida:
            room = session.room_partida
            start = session.start_min
            end = session.end_min
            on_date = session.session_date
        else:
            assignment = by_id.get(session.id)
            if assignment is None:
                continue
            room = assignment.room
            start = assignment.start_min
            end = start + session.duration_min
            on_date = remap_date(session.session_date, assignment.day)
        if not room:
            continue
        placed.append((session.id, on_date, start, end, room, session.unit))

    by_key: dict[tuple[date, str], list[tuple[str, int, int, str]]] = defaultdict(list)
    for sid, on_date, start, end, room, unit in placed:
        by_key[(on_date, room)].append((sid, start, end, unit))

    overlaps: list[RoomOverlap] = []
    for (on_date, room), items in by_key.items():
        items.sort(key=lambda row: row[1])
        for i, (left_id, left_start, left_end, left_unit) in enumerate(items):
            for right_id, right_start, right_end, right_unit in items[i + 1 :]:
                if left_end <= right_start:
                    break
                if left_unit == right_unit:
                    continue
                if not _time_overlap(left_start, left_end, right_start, right_end):
                    continue
                overlaps.append(
                    RoomOverlap(
                        room=room,
                        on_date=on_date,
                        left_id=left_id,
                        right_id=right_id,
                        left_start=left_start,
                        left_end=left_end,
                        right_start=right_start,
                        right_end=right_end,
                    )
                )
    overlaps.sort(key=lambda o: (o.on_date, o.room, o.left_id, o.right_id))
    return overlaps
