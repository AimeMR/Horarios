from pathlib import Path
from unittest.mock import patch

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.pipeline import _run_phase1

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_hybrid_passes_greedy_hints_to_phase1() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    greedy_hints = Phase1Result(
        True,
        {
            activity.id: data.sessions[activity.session_ids[0]].day
            for activity in data.activities.values()
        },
        {
            activity.id: data.sessions[activity.session_ids[0]].start_min
            for activity in data.activities.values()
        },
        "GREEDY",
        "greedy ok",
    )
    cpsat_ok = Phase1Result(
        True,
        dict(greedy_hints.activity_day),
        dict(greedy_hints.activity_start),
        "FEASIBLE",
        "phase1 ok",
    )
    with (
        patch(
            "horaris_solver.solver.pipeline.solve_phase1_greedy",
            return_value=greedy_hints,
        ) as spy_greedy,
        patch(
            "horaris_solver.solver.pipeline.solve_phase1",
            return_value=cpsat_ok,
        ) as spy_phase1,
    ):
        result = _run_phase1(data, strategy="hybrid", max_time_s=5)

    spy_greedy.assert_called_once_with(data)
    spy_phase1.assert_called_once()
    _args, kwargs = spy_phase1.call_args
    assert _args[0] is data
    assert kwargs.get("hints") is greedy_hints
    assert kwargs.get("stop_after_first_feasible") or kwargs.get("stop_after_first_solution")
    assert result is cpsat_ok
