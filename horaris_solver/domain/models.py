"""Immutable domain model mirroring official verifier semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

DIES = ("L", "M", "X", "J", "V")
MATI = (8 * 60 + 30, 14 * 60 + 30)  # 08:30–14:30
TARDA = (14 * 60 + 30, 21 * 60)  # 14:30–21:00, as in the verifier (R1-TORN: start < 14:30 is morning)
TIPUS_ORDINARIA = "Aules docents"
ONLINE_ACTIVITIES: frozenset[str] = frozenset()
ONLINE_ROOM = ""


def hm(value: str) -> int:
    hours, minutes = value.strip().split(":")
    return int(hours) * 60 + int(minutes)


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class Room:
    code: str
    building: str
    kind: str
    capacity: int
    description: str = ""

    @property
    def ordinary(self) -> bool:
        return self.kind == TIPUS_ORDINARIA

    @property
    def integrated(self) -> bool:
        return "integrat" in self.description.lower()


@dataclass(frozen=True)
class Session:
    id: str
    activity_id: str
    code: str
    kind: str
    group: str
    session_date: date
    day: str
    start_min: int
    duration_min: int
    students: int
    room_partida: str
    cohorts: tuple[str, ...]
    turn: str
    fixed: str
    teachers: frozenset[str]
    shared_id: str = ""
    sense_espai: bool = False
    online: bool = False

    @property
    def end_min(self) -> int:
        return self.start_min + self.duration_min

    @property
    def unit(self) -> str:
        return self.shared_id or self.id

    @property
    def group_number(self) -> str:
        return self.group.split("/")[-1]

    @property
    def line(self) -> str:
        number = self.group_number
        if self.kind == "TE":
            return number[:-1] if len(number) >= 3 and number.endswith("0") else number
        return number[:-1] if len(number) >= 3 else number


@dataclass(frozen=True)
class Activity:
    id: str
    code: str
    kind: str
    session_ids: tuple[str, ...]
    students: int
    turn: str
    fixed: str
    teachers: frozenset[str]
    cohorts: tuple[str, ...]
    duration_min: int
    sense_espai: bool = False


@dataclass(frozen=True)
class CalendarBlock:
    block_date: date
    start_min: int
    end_min: int
    reason: str


@dataclass(frozen=True)
class TimetableData:
    sessions: dict[str, Session]
    rooms: dict[str, Room]
    activities: dict[str, Activity]
    calendar: tuple[CalendarBlock, ...] = ()
    days_without_class: frozenset[date] = field(default_factory=frozenset)
    order: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolveRequest:
    semestre: int | None = None
    max_time_s: int = 300
    r8_soft_fallback: bool = True


@dataclass(frozen=True)
class Assignment:
    session_id: str
    day: str
    start_min: int
    room: str
