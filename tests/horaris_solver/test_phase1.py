from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.solver.phase1_time import solve_phase1

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_phase1_keeps_fixed_plab() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30)
    assert result.ok
    plab = data.activities["A4"]
    assert result.activity_day[plab.id] == data.sessions[plab.session_ids[0]].day
    assert result.activity_start[plab.id] == data.sessions[plab.session_ids[0]].start_min


def test_phase1_assigns_all_activities() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1(data, max_time_s=30)
    assert result.ok
    assert set(result.activity_day) == set(data.activities)
