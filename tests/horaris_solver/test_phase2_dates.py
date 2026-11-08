from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Assignment
from horaris_solver.solver.calendar_rules import remap_date
from horaris_solver.solver.phase1_time import expand_phase1_to_assignments, solve_phase1
from horaris_solver.solver.phase2_rooms import solve_phase2

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_two_mondays_may_share_room() -> None:
    """S00001 and S00002 are A1 on different Mondays — same room must be allowed."""
    data = CsvTimetableSource(FIXTURE).load()
    phase1 = solve_phase1(data, max_time_s=30)
    assert phase1.ok
    timed = expand_phase1_to_assignments(data, phase1)
    # Force same weekday/time as partida for A1 sessions
    forced = []
    for assignment in timed:
        session = data.sessions[assignment.session_id]
        if session.activity_id == "A1":
            forced.append(
                Assignment(
                    session_id=session.id,
                    day="L",
                    start_min=session.start_min,
                    room="",
                )
            )
        else:
            forced.append(assignment)
    phase2 = solve_phase2(data, forced, max_time_s=30)
    assert phase2.ok
    by_id = {a.session_id: a for a in phase2.assignments}
    d1 = remap_date(data.sessions["S00001"].session_date, by_id["S00001"].day)
    d2 = remap_date(data.sessions["S00002"].session_date, by_id["S00002"].day)
    assert d1 != d2
    # Same room is legal across weeks
    assert by_id["S00001"].room
    assert by_id["S00002"].room
