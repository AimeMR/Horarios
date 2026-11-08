from datetime import date

from horaris_solver.domain.models import Session


def test_line_and_unit() -> None:
    te = Session(
        id="S1",
        activity_id="A1",
        code="C",
        kind="TE",
        group="TE/81",
        session_date=date(2026, 9, 14),
        day="L",
        start_min=510,
        duration_min=120,
        students=10,
        room_partida="Q1/1011",
        cohorts=("GED:1r",),
        turn="mati",
        fixed="",
        teachers=frozenset({"D1"}),
    )
    assert te.line == "81"
    assert te.unit == "S1"

    shared = Session(
        id="S2",
        activity_id="A2",
        code="C",
        kind="TE",
        group="TE/81",
        session_date=date(2026, 9, 14),
        day="L",
        start_min=510,
        duration_min=120,
        students=10,
        room_partida="",
        cohorts=("GED:1r",),
        turn="mati",
        fixed="",
        teachers=frozenset({"D1"}),
        shared_id="SH1",
    )
    assert shared.unit == "SH1"
