from dataclasses import replace
from datetime import date

import pytest

from horaris_solver.domain.models import Assignment, Room, Session, TimetableData
from horaris_solver.solver.room_rules import (
    AULA_GENERAL,
    ESPAI_PRACTIQUES,
    allowed_room_kinds,
    room_candidates,
    room_kind_ok,
    unit_students,
)

ROOMS = {
    "A1": Room("A1", "A", "Aules docents", 60),
    "A2": Room("A2", "A", "Aules docents", 20),
    "S1": Room("S1", "A", "Seminaris", 30),
    "L1": Room("L1", "Q", "Laboratoris docents", 30),
    "L2": Room("L2", "Q", "Laboratoris docents", 30, "Laboratori integrat"),
    "I1": Room("I1", "Q", "Aules informàtiques", 30),
    "J/1": Room("J/1", "J", "Aules docents", 100),
}


def _session(kind: str, *, partida: str = "", students: int = 10, fixed: str = "", sense: bool = False) -> Session:
    return Session(
        id="S1",
        activity_id="A1",
        code="101",
        kind=kind,
        group="1",
        session_date=date(2026, 2, 2),
        day="Dilluns",
        start_min=600,
        duration_min=60,
        students=students,
        room_partida=partida,
        cohorts=("C1",),
        turn="M",
        fixed=fixed,
        teachers=frozenset(),
        sense_espai=sense,
    )


def _data(session: Session) -> TimetableData:
    return TimetableData(sessions={session.id: session}, rooms=ROOMS, activities={})


def test_te_in_lab_partida_falls_back_to_aula_general() -> None:
    session = _session("TE", partida="L1")
    assert allowed_room_kinds(_data(session), session) == AULA_GENERAL


def test_plab_without_partida_uses_espai_practiques() -> None:
    session = _session("PLAB")
    assert allowed_room_kinds(_data(session), session) == ESPAI_PRACTIQUES


def test_plab_in_lab_partida_keeps_lab_kind() -> None:
    session = _session("PLAB", partida="L1")
    assert allowed_room_kinds(_data(session), session) == frozenset({"Laboratoris docents"})


def test_paul_allowed_in_integrated_lab_and_informatiques() -> None:
    session = _session("PAUL")
    data = _data(session)
    assert room_kind_ok(data, session, "L2")
    assert room_kind_ok(data, session, "I1")
    assert not room_kind_ok(data, session, "L1")


def test_te_rejects_lab_room() -> None:
    session = _session("TE")
    assert not room_kind_ok(_data(session), session, "L1")


def test_candidates_exclude_j_rooms() -> None:
    session = _session("TE")
    candidates = room_candidates(_data(session), session)
    assert "J/1" not in candidates
    assert set(candidates) == {"A1", "A2", "S1"}


def test_candidates_filter_by_capacity() -> None:
    session = _session("TE", students=40)
    assert room_candidates(_data(session), session) == ["A1"]


def test_movable_session_does_not_get_too_small_partida() -> None:
    session = _session("TE", partida="A2", students=40)
    assert room_candidates(_data(session), session) == ["A1"]


def test_movable_session_keeps_partida_that_fits() -> None:
    session = _session("TE", partida="A2", students=15)
    assert "A2" in room_candidates(_data(session), session)


@pytest.mark.parametrize("fixed", ["R1", "R7"])
def test_pinned_session_keeps_too_small_partida(fixed: str) -> None:
    session = _session("TE", partida="A2", students=40, fixed=fixed)
    timed = {"S1": Assignment("S1", session.day, session.start_min, "")}
    assert room_candidates(_data(session), session, timed) == ["A2"]


def test_shared_unit_capacity_uses_sum_of_students() -> None:
    left = replace(_session("TE", students=15), shared_id="U")
    right = replace(left, id="S2")
    data = TimetableData(sessions={left.id: left, right.id: right}, rooms=ROOMS, activities={})
    assert set(room_candidates(data, left)) == {"A1", "S1"}
    assert set(room_candidates(data, left, unit_load=unit_students(data))) == {"A1", "S1"}


def test_unit_students_ignores_sense_espai_sessions() -> None:
    left = replace(_session("TE", students=15), shared_id="U")
    right = replace(left, id="S2", sense_espai=True)
    data = TimetableData(sessions={left.id: left, right.id: right}, rooms=ROOMS, activities={})
    assert unit_students(data) == {"U": 15}


def test_no_fitting_room_falls_back_to_largest_valid_rooms() -> None:
    session = _session("TE", partida="A2", students=100)
    assert room_candidates(_data(session), session) == ["A1"]


def test_r7_unchanged_time_keeps_only_partida() -> None:
    session = _session("PLAB", partida="L1", fixed="R7")
    timed = {"S1": Assignment("S1", session.day, session.start_min, "")}
    assert room_candidates(_data(session), session, timed) == ["L1"]
    assert room_candidates(_data(session), session) == ["L1"]


def test_r7_moved_time_opens_other_rooms() -> None:
    session = _session("PLAB", partida="L1", fixed="R7")
    timed = {"S1": Assignment("S1", "Dimarts", session.start_min, "")}
    assert set(room_candidates(_data(session), session, timed)) == {"L1", "L2"}


def test_r7_plab_keeps_external_j_partida_room() -> None:
    session = _session("PLAB", partida="J/012", fixed="R7")
    timed = {"S1": Assignment("S1", session.day, session.start_min, "")}
    assert room_candidates(_data(session), session, timed) == ["J/012"]


def test_r7_non_plab_in_j_room_is_not_pinned() -> None:
    session = _session("TE", partida="J/012", fixed="R7")
    timed = {"S1": Assignment("S1", session.day, session.start_min, "")}
    assert set(room_candidates(_data(session), session, timed)) == {"A1", "A2", "S1"}


def test_r7_plab_without_partida_has_no_room() -> None:
    session = _session("PLAB", fixed="R7")
    assert room_candidates(_data(session), session) == [""]


def test_sense_espai_returns_empty_room() -> None:
    session = _session("TE", sense=True)
    assert room_candidates(_data(session), session) == [""]


def test_zero_students_skips_capacity_filter() -> None:
    session = replace(_session("TE"), students=0)
    assert set(room_candidates(_data(session), session)) == {"A1", "A2", "S1"}


def test_r1_unchanged_time_keeps_only_partida() -> None:
    session = _session("TE", partida="A2", fixed="R1")
    timed = {"S1": Assignment("S1", session.day, session.start_min, "")}
    assert room_candidates(_data(session), session, timed) == ["A2"]
    assert room_candidates(_data(session), session) == ["A2"]


def test_r1_moved_time_opens_other_rooms() -> None:
    session = _session("TE", partida="A2", fixed="R1")
    timed = {"S1": Assignment("S1", "Dimarts", session.start_min, "")}
    assert set(room_candidates(_data(session), session, timed)) == {"A1", "A2", "S1"}


def test_r1_in_j_room_is_not_pinned() -> None:
    session = _session("TE", partida="J/1", fixed="R1")
    assert {"A1", "A2", "S1"} <= set(room_candidates(_data(session), session))


def test_r1_sense_espai_has_no_room() -> None:
    session = _session("TE", partida="A2", fixed="R1", sense=True)
    assert room_candidates(_data(session), session) == [""]


def test_r1_without_partida_gets_any_valid_room() -> None:
    session = _session("TE", fixed="R1")
    assert set(room_candidates(_data(session), session)) == {"A1", "A2", "S1"}


def test_r1_with_unknown_partida_room_is_not_pinned() -> None:
    session = _session("TE", partida="X/9999", fixed="R1")
    assert set(room_candidates(_data(session), session)) == {"A1", "A2", "S1"}
