from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.solver.phase1_time import expand_phase1_to_assignments, solve_phase1
from horaris_solver.solver.phase2_rooms import solve_phase2

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_phase2_assigns_rooms_and_keeps_plab() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    phase1 = solve_phase1(data, max_time_s=30)
    assert phase1.ok
    timed = expand_phase1_to_assignments(data, phase1)
    phase2 = solve_phase2(data, timed, max_time_s=30)
    assert phase2.ok
    by_id = {a.session_id: a for a in phase2.assignments}
    assert by_id["S00005"].room == "Q5/0001"
    for sid, assignment in by_id.items():
        session = data.sessions[sid]
        if session.sense_espai:
            continue
        assert assignment.room
