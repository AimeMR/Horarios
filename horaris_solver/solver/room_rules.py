"""Room-type rules shared by the room-assignment models (pure functions)."""

from __future__ import annotations

from collections.abc import Mapping

from horaris_solver.domain.models import Assignment, Session, TimetableData

AULA_GENERAL = frozenset({"Aules docents", "Seminaris"})
ESPAI_PRACTIQUES = frozenset({"Laboratoris docents", "Aules informàtiques"})
RESERVA_MIN = 2
ROOM_PREFIX_TO_MOVE = "J/"


def allowed_room_kinds(data: TimetableData, session: Session) -> frozenset[str]:
    """Room kinds a session may use, derived from its partida room and kind."""
    if session.room_partida in data.rooms:
        kind = data.rooms[session.room_partida].kind
        if kind == "Laboratoris docents" and session.kind != "PLAB":
            return AULA_GENERAL
        return AULA_GENERAL if kind in AULA_GENERAL else frozenset({kind})
    return ESPAI_PRACTIQUES if session.kind == "PLAB" else AULA_GENERAL


def room_kind_ok(data: TimetableData, session: Session, room_code: str) -> bool:
    """True when the room's kind is acceptable for the session."""
    room = data.rooms[room_code]
    if session.kind == "PAUL" and (room.integrated or room.kind == "Aules informàtiques"):
        return True
    return room.kind in allowed_room_kinds(data, session)


def r7_time_unchanged(session: Session, timed: dict[str, Assignment] | None) -> bool:
    """True when an R7 session keeps its partida day and start time."""
    if timed is None or session.id not in timed:
        return True
    assignment = timed[session.id]
    return assignment.day == session.day and assignment.start_min == session.start_min


def r7_room_pinned(session: Session, timed: dict[str, Assignment] | None) -> bool:
    """True when an R7 session must keep its partida room (verifier R7-PLAB).

    A PLAB keeps its room even outside the aulari (J/ or unknown); any other session in a J/ room
    is to be moved out, which the verifier does not count as a move.
    """
    partida = session.room_partida
    return (
        session.fixed.startswith("R7")
        and bool(partida)
        and (session.kind == "PLAB" or not partida.startswith(ROOM_PREFIX_TO_MOVE))
        and r7_time_unchanged(session, timed)
    )


def r1_room_pinned(data: TimetableData, session: Session, timed: dict[str, Assignment] | None) -> bool:
    """True when a non-PLAB R1 session must keep its partida room (verifier R1-FIXADA)."""
    partida = session.room_partida
    return (
        session.fixed.startswith("R1")
        and session.kind != "PLAB"
        and not session.sense_espai
        and bool(partida)
        and not partida.startswith(ROOM_PREFIX_TO_MOVE)
        and partida in data.rooms
        and r7_time_unchanged(session, timed)
    )


def unit_students(data: TimetableData) -> dict[str, int]:
    """Students per shared unit, summed over sessions that need a room (verifier R3-AFORAMENT)."""
    totals: dict[str, int] = {}
    for session in data.sessions.values():
        if session.sense_espai:
            continue
        totals[session.unit] = totals.get(session.unit, 0) + session.students
    return totals


def room_candidates(
    data: TimetableData,
    session: Session,
    timed: dict[str, Assignment] | None = None,
    unit_load: Mapping[str, int] | None = None,
) -> list[str]:
    """Room codes a session may be placed in ("" means no room).

    Pinned sessions (R7 unchanged, R1 room-pinned) keep their partida room even when it is too
    small: the verifier inherits those violations. A movable session only gets rooms that fit its
    whole shared unit; when none fits, it falls back to the largest valid-kind rooms so phase 2
    still produces a schedule and the verifier reports the R3-AFORAMENT instead of crashing.
    """
    if session.sense_espai:
        return [""]
    if session.kind == "PLAB" and session.fixed.startswith("R7") and not session.room_partida:
        return [""]
    # Keep partida lab only when day/time were not repaired away from partida.
    if r7_room_pinned(session, timed):
        return [session.room_partida]
    if r1_room_pinned(data, session, timed):
        return [session.room_partida]
    valid = [
        room
        for room in data.rooms.values()
        if room_kind_ok(data, session, room.code) and not room.code.startswith(ROOM_PREFIX_TO_MOVE)
    ]
    loads = unit_load if unit_load is not None else unit_students(data)
    needed = max(loads.get(session.unit, 0), session.students)
    fitting = [room.code for room in valid if needed <= 0 or room.capacity >= needed]
    partida = data.rooms.get(session.room_partida)
    if (
        partida is not None
        and partida.code not in fitting
        and room_kind_ok(data, session, partida.code)
        and (needed <= 0 or partida.capacity >= needed)
    ):
        fitting.append(partida.code)
    if fitting or not valid:
        return fitting
    largest = max(room.capacity for room in valid)
    return [room.code for room in valid if room.capacity == largest]
