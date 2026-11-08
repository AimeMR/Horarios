import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.solver import pipeline
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.phase2_rooms import Phase2Result
from horaris_solver.solver.pipeline import _run_phase1

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_hybrid_passes_greedy_hints_to_phase1() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    greedy_hints = Phase1Result(
        True,
        {activity.id: data.sessions[activity.session_ids[0]].day for activity in data.activities.values()},
        {activity.id: data.sessions[activity.session_ids[0]].start_min for activity in data.activities.values()},
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


@pytest.mark.parametrize("strategy", ["hybrid", "greedy", "cpsat"])
@pytest.mark.parametrize("budget", [1, 10, 59, 300])
def test_phase_budgets_sum_to_at_most_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, budget: int, strategy: str
) -> None:
    data = CsvTimetableSource(FIXTURE).load()
    captured: dict[str, Any] = {}

    def fake_phase1(_data: object, *, strategy: str, max_time_s: float) -> Phase1Result:
        captured["p1"] = max_time_s
        captured["strategy"] = strategy
        return Phase1Result(True, {}, {}, "FEASIBLE", "ok")

    def fake_phase2(_data: object, _timed: object, *, max_time_s: float, r8_soft_fallback: bool) -> Phase2Result:
        captured["p2"] = max_time_s
        return Phase2Result(True, [], "OPTIMAL", "ok")

    monkeypatch.setattr(pipeline, "_load_data", lambda **_kwargs: data)
    monkeypatch.setattr(pipeline, "_run_phase1", fake_phase1)
    monkeypatch.setattr(pipeline, "expand_phase1_to_assignments", lambda *_args: [])
    monkeypatch.setattr(pipeline, "solve_phase2", fake_phase2)

    result = pipeline.solve_and_export(out_csv=tmp_path / "out.csv", max_time_s=budget, strategy=strategy)

    assert result.ok
    assert captured["strategy"] == strategy
    assert captured["p1"] > 0 and captured["p2"] > 0
    assert captured["p1"] + captured["p2"] <= budget
    assert captured["p1"] == pytest.approx(budget / 2)


def test_hybrid_drops_hints_when_greedy_has_violations() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    invalid_greedy = Phase1Result(True, {}, {}, "GREEDY", "greedy claims ok but placed nothing")
    cpsat_fail = Phase1Result(False, {}, {}, "UNKNOWN", "timeout")
    with (
        patch("horaris_solver.solver.pipeline.solve_phase1_greedy", return_value=invalid_greedy),
        patch("horaris_solver.solver.pipeline.solve_phase1", return_value=cpsat_fail) as spy_phase1,
    ):
        result = _run_phase1(data, strategy="hybrid", max_time_s=5)

    assert spy_phase1.call_args.kwargs.get("hints") is None
    assert result.status == "GREEDY_FALLBACK"


def test_run_phase1_rejects_portfolio_strategy() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    with pytest.raises(ValueError, match="portfolio"):
        _run_phase1(data, strategy="portfolio", max_time_s=5)


def test_hybrid_writes_deficit_csv_and_json_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = CsvTimetableSource(FIXTURE).load()
    monkeypatch.setattr(pipeline, "_load_data", lambda **_kwargs: data)
    monkeypatch.setattr(pipeline, "_run_phase1", lambda _d, **_k: Phase1Result(True, {}, {}, "FEASIBLE", "ok"))
    monkeypatch.setattr(pipeline, "expand_phase1_to_assignments", lambda *_args: [])
    monkeypatch.setattr(pipeline, "solve_phase2", lambda *_a, **_k: Phase2Result(True, [], "OPTIMAL", "ok"))
    deficit = tmp_path / "deficit.csv"
    json_out = tmp_path / "out.json"

    result = pipeline.solve_and_export(
        out_csv=tmp_path / "out.csv", max_time_s=10, strategy="hybrid", deficit_out=deficit, json_out=json_out
    )

    assert result.ok
    assert result.stage_reports == ()
    lines = deficit.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "codi,tipus,max_simultanies,docents_reals,deficit,data_pic,franja_pic"
    metrics = json.loads(json_out.read_text(encoding="utf-8"))["metrics"]
    assert len(metrics["deficit"]) == len(lines) - 1
    teacher_names = {t for s in data.sessions.values() for t in s.teachers}
    assert not teacher_names & {str(v) for row in metrics["deficit"] for v in row.values()}


def test_hybrid_without_deficit_out_writes_no_deficit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = CsvTimetableSource(FIXTURE).load()
    monkeypatch.setattr(pipeline, "_load_data", lambda **_kwargs: data)
    monkeypatch.setattr(pipeline, "_run_phase1", lambda _d, **_k: Phase1Result(True, {}, {}, "FEASIBLE", "ok"))
    monkeypatch.setattr(pipeline, "expand_phase1_to_assignments", lambda *_args: [])
    monkeypatch.setattr(pipeline, "solve_phase2", lambda *_a, **_k: Phase2Result(True, [], "OPTIMAL", "ok"))
    json_out = tmp_path / "out.json"

    pipeline.solve_and_export(out_csv=tmp_path / "out.csv", max_time_s=10, json_out=json_out)

    assert "deficit" not in json.loads(json_out.read_text(encoding="utf-8"))["metrics"]


def test_hybrid_partial_phase2_writes_csv_but_is_not_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = CsvTimetableSource(FIXTURE).load()
    partial = Phase2Result(
        True,
        [],
        "FEASIBLE",
        "phase2 partial unassigned=2",
        True,
        unassigned=("HIDDEN-ID-1", "HIDDEN-ID-2"),
    )
    monkeypatch.setattr(pipeline, "_load_data", lambda **_kwargs: data)
    monkeypatch.setattr(pipeline, "_run_phase1", lambda _d, **_k: Phase1Result(True, {}, {}, "FEASIBLE", "ok"))
    monkeypatch.setattr(pipeline, "expand_phase1_to_assignments", lambda *_args: [])
    monkeypatch.setattr(pipeline, "solve_phase2", lambda *_a, **_k: partial)
    out = tmp_path / "out.csv"
    json_out = tmp_path / "out.json"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=10, strategy="hybrid", json_out=json_out)

    assert not result.ok
    assert out.is_file()
    assert "partial: unassigned_rooms=2" in result.summary
    assert "HIDDEN-ID" not in result.summary
    text = json_out.read_text(encoding="utf-8")
    assert json.loads(text)["metrics"]["unassigned_rooms"] == 2
    assert "HIDDEN-ID" not in text
