"""Room overlap audit (R4-AULA style)."""

from datetime import date

from horaris_solver.audit.overlaps import find_room_overlaps
from horaris_solver.domain.models import Assignment, Room, Session, TimetableData


def _session(
    sid: str,
    *,
    start: int,
    room: str,
    shared: str = "",
    day: str = "L",
) -> Session:
    return Session(
        id=sid,
        activity_id=f"A{sid}",
        code="C",
        kind="TE",
        group="TE/11",
        session_date=date(2026, 9, 14),
        day=day,
        start_min=start,
        duration_min=60,
        students=10,
        room_partida=room,
        cohorts=("GEI:1r",),
        turn="mati",
        fixed="",
        teachers=frozenset({"D1"}),
        shared_id=shared,
    )


def test_detects_distinct_unit_room_clash() -> None:
    data = TimetableData(
        sessions={
            "S1": _session("S1", start=510, room="Q1/1003"),
            "S2": _session("S2", start=530, room="Q1/1003"),
        },
        rooms={"Q1/1003": Room("Q1/1003", "Q1", "Aules docents", 40)},
        activities={},
    )
    overlaps = find_room_overlaps(data, use_partida=True)
    assert len(overlaps) == 1
    assert overlaps[0].room == "Q1/1003"


def test_shared_unit_same_room_not_overlap() -> None:
    data = TimetableData(
        sessions={
            "S1": _session("S1", start=510, room="Q1/1003", shared="SH"),
            "S2": _session("S2", start=510, room="Q1/1003", shared="SH"),
        },
        rooms={"Q1/1003": Room("Q1/1003", "Q1", "Aules docents", 40)},
        activities={},
    )
    assert find_room_overlaps(data, use_partida=True) == []


def test_proposal_audit_uses_assignment_room() -> None:
    data = TimetableData(
        sessions={
            "S1": _session("S1", start=510, room="Q1/1003"),
            "S2": _session("S2", start=510, room="Q1/1003"),
        },
        rooms={
            "Q1/1003": Room("Q1/1003", "Q1", "Aules docents", 40),
            "Q2/1003": Room("Q2/1003", "Q2", "Aules docents", 40),
        },
        activities={},
    )
    ok = [
        Assignment("S1", "L", 510, "Q1/1003"),
        Assignment("S2", "L", 510, "Q2/1003"),
    ]
    assert find_room_overlaps(data, ok) == []
    bad = [
        Assignment("S1", "L", 510, "Q1/1003"),
        Assignment("S2", "L", 510, "Q1/1003"),
    ]
    assert len(find_room_overlaps(data, bad)) == 1
