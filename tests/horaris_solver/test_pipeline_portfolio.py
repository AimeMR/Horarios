import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.audit.overlaps import RoomOverlap
from horaris_solver.domain.models import Assignment, TimetableData
from horaris_solver.solver import pipeline
from horaris_solver.solver.budget import Deadline, PortfolioBudget, split_portfolio
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.phase2_rooms import Phase2Result
from horaris_solver.solver.portfolio import PortfolioConfig, PortfolioResult
from horaris_solver.solver.rules import Phase1Rules
from horaris_solver.solver.violations import Violation

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


@pytest.fixture
def data() -> TimetableData:
    return CsvTimetableSource(FIXTURE).load()


def _partida_map(data: TimetableData, status: str = "FEASIBLE", ok: bool = True) -> Phase1Result:
    return Phase1Result(
        ok,
        {a.id: data.sessions[a.session_ids[0]].day for a in data.activities.values()},
        {a.id: data.sessions[a.session_ids[0]].start_min for a in data.activities.values()},
        status,
        "msg",
    )


def _portfolio_result(best: Phase1Result, ranked: tuple[Phase1Result, ...]) -> PortfolioResult:
    return PortfolioResult(best=best, ranked=ranked, candidates=(), n_effective=2, stages=("precheck:ok",))


class _Phase2Script:
    """Fake solve_phase2 returning scripted results in order and recording the phase-1 input."""

    def __init__(self, results: list[Phase2Result]) -> None:
        self.results = list(results)
        self.calls: list[list[Assignment]] = []

    def __call__(
        self, _data: object, timed: list[Assignment], *, max_time_s: float, r8_soft_fallback: bool
    ) -> Phase2Result:
        assert max_time_s > 0
        self.calls.append(timed)
        return self.results.pop(0)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    data: TimetableData,
    portfolio: PortfolioResult,
    phase2: _Phase2Script,
) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_run_portfolio(
        _data: object, *, config: PortfolioConfig, budget: PortfolioBudget, rules: object
    ) -> PortfolioResult:
        seen["config"] = config
        seen["budget"] = budget
        return portfolio

    monkeypatch.setattr(pipeline, "_load_data", lambda **_kwargs: data)
    monkeypatch.setattr(pipeline, "run_portfolio", fake_run_portfolio)
    monkeypatch.setattr(pipeline, "solve_phase2", phase2)
    return seen


def _ok_phase2() -> Phase2Result:
    return Phase2Result(True, [], "OPTIMAL", "ok")


def test_portfolio_happy_path_writes_csv_json_and_stage_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    best = _partida_map(data)
    phase2 = _Phase2Script([_ok_phase2()])
    config = PortfolioConfig(seed=7, size=4, top_k=2)
    seen = _install(monkeypatch, data, _portfolio_result(best, (best,)), phase2)
    out = tmp_path / "out.csv"
    json_out = tmp_path / "out.json"

    result = pipeline.solve_and_export(
        out_csv=out, max_time_s=20, strategy="portfolio", portfolio=config, json_out=json_out
    )

    assert result.ok, result.summary
    assert out.is_file()
    assert seen["config"] == config
    assert any(r.startswith("phase2[0]") for r in result.stage_reports)
    assert "audit: new_room_overlaps=0 new_cohort_clashes=0" in result.stage_reports
    metrics = json.loads(json_out.read_text(encoding="utf-8"))["metrics"]
    assert metrics["seed"] == 7 and metrics["size"] == 4 and metrics["top_k"] == 2
    assert metrics["n_effective"] == 2
    assert metrics["winner_status"] == "FEASIBLE"
    assert set(metrics["phase1_score"]) >= {"hard", "unplaced", "soft"}
    assert metrics["stage_reports"] == list(result.stage_reports)


def test_portfolio_defaults_config_when_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    best = _partida_map(data)
    seen = _install(monkeypatch, data, _portfolio_result(best, (best,)), _Phase2Script([_ok_phase2()]))

    pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert seen["config"] == PortfolioConfig()


@pytest.mark.parametrize("budget", [1, 10, 19])
def test_portfolio_rejects_budget_below_20(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, budget: int) -> None:
    def boom(**_kwargs: object) -> TimetableData:
        raise AssertionError("must not load data")

    monkeypatch.setattr(pipeline, "_load_data", boom)
    out = tmp_path / "out.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=budget, strategy="portfolio")

    assert not result.ok
    assert result.summary == "portfolio needs --max-time >= 20"
    assert not out.exists()


def test_unknown_strategy_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="strategy must be one of"):
        pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="evil;rm")


def test_portfolio_propagates_infeasible_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    best = Phase1Result(False, {}, {}, "INFEASIBLE_DATA", "precheck blocking: A1")
    phase2 = _Phase2Script([])
    _install(monkeypatch, data, _portfolio_result(best, ()), phase2)
    out = tmp_path / "out.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    assert not result.ok
    assert "INFEASIBLE_DATA" in result.summary and "precheck blocking" in result.summary
    assert not out.exists()
    assert phase2.calls == []


_STEPS = ("RELAXED_D7", "RELAXED_D6_D7", "RELAXED_R4")
_D7_OFF = Phase1Rules(same_kind_day=False, room_pools=True)


class _Ladder:
    """Fake greedy + CP-SAT per ladder step; ``ok_steps`` maps a step name to "cpsat" or "greedy" success."""

    def __init__(
        self,
        data: TimetableData,
        ok_steps: dict[str, str],
        clock: list[float] | None = None,
        steps: tuple[str, ...] = ("RELAXED_D7", "RELAXED_D6_D7", "RELAXED_R4"),
    ) -> None:
        self.data = data
        self.steps = steps
        self.ok_steps = ok_steps
        self.clock = clock
        self.greedy_calls: list[dict[str, Any]] = []
        self.cpsat_calls: list[dict[str, Any]] = []
        self.remaining_at_call: list[float] = []

    def greedy(self, _data: object, **kwargs: Any) -> Phase1Result:
        step = self.steps[len(self.greedy_calls)]
        self.greedy_calls.append(kwargs)
        return _partida_map(self.data, status="GREEDY", ok=self.ok_steps.get(step) == "greedy")

    def cpsat(self, _data: object, **kwargs: Any) -> Phase1Result:
        step = self.steps[len(self.cpsat_calls)]
        self.cpsat_calls.append(kwargs)
        if self.clock is not None:
            self.remaining_at_call.append(100.0 - self.clock[0])
            self.clock[0] += kwargs["max_time_s"]
        if self.ok_steps.get(step) == "cpsat":
            return _partida_map(self.data, status="OPTIMAL")
        return Phase1Result(False, {}, {}, "INFEASIBLE", "no")


def _fake_validate(_data: object, result: Phase1Result, _rules: object = None) -> list[Violation]:
    return [] if result.ok else [Violation("MISSING", ("x",))]


def _install_ladder(monkeypatch: pytest.MonkeyPatch, ladder: _Ladder) -> None:
    monkeypatch.setattr(pipeline, "solve_phase1_greedy", ladder.greedy)
    monkeypatch.setattr(pipeline, "solve_phase1", ladder.cpsat)
    monkeypatch.setattr(pipeline, "validate_phase1", _fake_validate)


_FAILED_BEST = Phase1Result(False, {}, {}, "INFEASIBLE", "portfolio found no valid schedule")


def _run_relaxed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    data: TimetableData,
    ladder: _Ladder,
    phase2: list[Phase2Result],
) -> tuple[pipeline.SolveExportResult, dict[str, Any] | None]:
    _install(monkeypatch, data, _portfolio_result(_FAILED_BEST, ()), _Phase2Script(phase2))
    _install_ladder(monkeypatch, ladder)
    json_out = tmp_path / "o.json"
    result = pipeline.solve_and_export(
        out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio", json_out=json_out
    )
    metrics = json.loads(json_out.read_text(encoding="utf-8"))["metrics"] if json_out.is_file() else None
    return result, metrics


def test_relax_ladder_step1_success_reports_d7(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_D7": "cpsat", "RELAXED_D6_D7": "cpsat"})
    fake = [Violation("D7-SAME-KIND-DAY", ("a", "b")), Violation("D7-SAME-KIND-DAY", ("c", "d"))]
    monkeypatch.setattr(pipeline, "sibling_violations", lambda _d, _days: fake)

    result, metrics = _run_relaxed(monkeypatch, tmp_path, data, ladder, [_ok_phase2()])

    assert result.ok, result.summary
    assert "phase1=RELAXED_D7" in result.summary
    assert len(ladder.cpsat_calls) == 1
    call = ladder.cpsat_calls[0]
    assert call["rules"] == _D7_OFF and call["soft_overlap"] is False and call["hints"] is None
    assert ladder.greedy_calls[0]["rules"] == _D7_OFF
    assert "relax:RELAXED_D7 OPTIMAL" in result.stage_reports
    assert "relax: d7_violations=2" in result.stage_reports
    assert not any("d6_violations" in r for r in result.stage_reports)
    assert metrics is not None
    assert metrics["phase1"] == "RELAXED_D7" and metrics["winner_status"] == "RELAXED_D7"
    assert metrics["d7_violations"] == 2
    assert "d6_violations" not in metrics


def test_relax_ladder_valid_greedy_is_hint_and_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_D7": "greedy"})

    result, metrics = _run_relaxed(monkeypatch, tmp_path, data, ladder, [_ok_phase2()])

    assert result.ok, result.summary
    assert "phase1=RELAXED_D7" in result.summary
    assert len(ladder.cpsat_calls) == 1
    assert ladder.cpsat_calls[0]["hints"] is not None
    assert "relax:RELAXED_D7 INFEASIBLE greedy=ok" in result.stage_reports
    assert metrics is not None and "d7_violations" in metrics


def test_relax_ladder_step2_when_step1_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_D6_D7": "cpsat", "RELAXED_R4": "cpsat"})
    monkeypatch.setattr(pipeline, "pool_violations", lambda _d, _days, _starts: [Violation("D6-POOL", ("a",))])

    result, metrics = _run_relaxed(monkeypatch, tmp_path, data, ladder, [_ok_phase2()])

    assert result.ok, result.summary
    assert "phase1=RELAXED_D6_D7" in result.summary
    assert [c["rules"] for c in ladder.cpsat_calls] == [_D7_OFF, None]
    assert [c["soft_overlap"] for c in ladder.cpsat_calls] == [False, False]
    assert "relax:RELAXED_D7 INFEASIBLE" in result.stage_reports
    assert "relax:RELAXED_D6_D7 OPTIMAL" in result.stage_reports
    assert "relax: d6_violations=1" in result.stage_reports
    assert metrics is not None and metrics["d6_violations"] == 1 and "d7_violations" in metrics


def test_relax_ladder_step3_r4_when_others_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_R4": "cpsat"})

    result, metrics = _run_relaxed(monkeypatch, tmp_path, data, ladder, [_ok_phase2()])

    assert result.ok, result.summary
    assert "phase1=RELAXED_R4" in result.summary
    assert len(ladder.cpsat_calls) == 3
    last = ladder.cpsat_calls[-1]
    assert last["rules"] is None and last["soft_overlap"] is True
    assert all(c["random_seed"] == 0 and c["deterministic"] is False for c in ladder.cpsat_calls)
    assert metrics is not None and metrics["phase1"] == "RELAXED_R4"
    assert "d6_violations" in metrics and "d7_violations" in metrics


def test_relax_ladder_all_fail_lists_step_statuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {})

    result, metrics = _run_relaxed(monkeypatch, tmp_path, data, ladder, [])

    assert not result.ok
    assert result.summary.startswith("phase1 failed: INFEASIBLE portfolio found no valid schedule")
    assert "relax: RELAXED_D7=INFEASIBLE, RELAXED_D6_D7=INFEASIBLE, RELAXED_R4=INFEASIBLE" in result.summary
    assert [r for r in result.stage_reports if r.startswith("relax")] == [f"relax:{s} INFEASIBLE" for s in _STEPS]
    assert metrics is None
    assert not (tmp_path / "o.csv").exists()


def test_relax_ladder_slices_never_exceed_remaining(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    clock = [0.0]
    ladder = _Ladder(data, {}, clock=clock)
    monkeypatch.setattr(pipeline, "Deadline", lambda _total: Deadline(100.0, clock=lambda: clock[0]))
    _install(monkeypatch, data, _portfolio_result(_FAILED_BEST, ()), _Phase2Script([]))
    _install_ladder(monkeypatch, ladder)

    pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert len(ladder.cpsat_calls) == 3
    for call, remaining in zip(ladder.cpsat_calls, ladder.remaining_at_call, strict=True):
        assert 1 <= call["max_time_s"] <= remaining
    for greedy, call in zip(ladder.greedy_calls, ladder.cpsat_calls, strict=True):
        assert greedy["repair_time_s"] <= min(45.0, call["max_time_s"] / 4)
    assert clock[0] <= 100.0 - split_portfolio(20.0).phase2_s + 1e-9


def test_relax_ladder_skips_steps_without_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_D7": "cpsat"})
    monkeypatch.setattr(pipeline, "Deadline", lambda _total: Deadline(0.5, clock=lambda: 0.0))
    _install(monkeypatch, data, _portfolio_result(_FAILED_BEST, ()), _Phase2Script([]))
    _install_ladder(monkeypatch, ladder)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert not result.ok
    assert ladder.cpsat_calls == [] and ladder.greedy_calls == []
    assert [r for r in result.stage_reports if r.startswith("relax")] == [f"relax:{s} SKIPPED" for s in _STEPS]
    assert "RELAXED_R4=SKIPPED" in result.summary


@pytest.mark.parametrize(
    "best",
    [
        Phase1Result(False, {}, {}, "INFEASIBLE_DATA", "precheck blocking: A1"),
        Phase1Result(True, {}, {}, "OPTIMAL", "ok"),
    ],
)
def test_relax_ladder_not_run_when_best_ok_or_infeasible_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData, best: Phase1Result
) -> None:
    ladder = _Ladder(data, {"RELAXED_D7": "cpsat"})
    ranked = (_partida_map(data, status="OPTIMAL"),) if best.ok else ()
    _install(monkeypatch, data, _portfolio_result(best, ranked), _Phase2Script([_ok_phase2()]))
    _install_ladder(monkeypatch, ladder)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert ladder.cpsat_calls == [] and ladder.greedy_calls == []
    assert not any(r.startswith("relax") for r in result.stage_reports)


def test_portfolio_phase2_failure_retries_next_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    first = _partida_map(data, status="OPTIMAL")
    second = _partida_map(data, status="GREEDY_FALLBACK")
    phase2 = _Phase2Script([Phase2Result(False, [], "INFEASIBLE", "rooms"), _ok_phase2()])
    _install(monkeypatch, data, _portfolio_result(first, (first, second)), phase2)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert result.ok, result.summary
    assert len(phase2.calls) == 2
    assert "phase1=GREEDY_FALLBACK" in result.summary
    assert result.stage_reports[-3].startswith("phase2[0]") and "ok=False" in result.stage_reports[-3]
    assert result.stage_reports[-2].startswith("phase2[1]")


def test_portfolio_phase2_all_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData) -> None:
    best = _partida_map(data)
    phase2 = _Phase2Script([Phase2Result(False, [], "INFEASIBLE", "rooms")])
    _install(monkeypatch, data, _portfolio_result(best, (best,)), phase2)
    out = tmp_path / "o.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    assert not result.ok
    assert result.summary.startswith("phase2 failed: INFEASIBLE")
    assert not out.exists()


def test_portfolio_audit_new_overlaps_exports_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    best = _partida_map(data)
    _install(monkeypatch, data, _portfolio_result(best, (best,)), _Phase2Script([_ok_phase2()]))
    new = RoomOverlap("A1", date(2025, 9, 15), "S-new-1", "S-new-2", 540, 600, 570, 630)
    inherited = RoomOverlap("A1", date(2025, 9, 15), "S-old-1", "S-old-2", 540, 600, 570, 630)

    def fake_overlaps(_data: object, assignments: object = None, *, use_partida: bool = False) -> list[RoomOverlap]:
        return [inherited] if use_partida else [inherited, new]

    monkeypatch.setattr(pipeline, "find_room_overlaps", fake_overlaps)
    monkeypatch.setattr(pipeline, "find_cohort_clashes", lambda *_a, **_k: [])
    out = tmp_path / "o.csv"
    json_out = tmp_path / "o.json"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio", json_out=json_out)

    assert not result.ok
    assert out.is_file()
    assert result.summary.startswith("diagnostic export: new_room_overlaps=1 new_cohort_clashes=0")
    assert "audit: new_room_overlaps=1 new_cohort_clashes=0" in result.stage_reports
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status"] == "diagnostic"
    assert payload["metrics"]["new_room_overlaps"] == 1


def test_portfolio_deficit_written_without_teacher_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    best = _partida_map(data)
    _install(monkeypatch, data, _portfolio_result(best, (best,)), _Phase2Script([_ok_phase2()]))
    deficit = tmp_path / "deficit.csv"
    json_out = tmp_path / "o.json"

    result = pipeline.solve_and_export(
        out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio", deficit_out=deficit, json_out=json_out
    )

    assert result.ok, result.summary
    assert deficit.read_text(encoding="utf-8").startswith("codi,tipus,max_simultanies")
    rows = json.loads(json_out.read_text(encoding="utf-8"))["metrics"]["deficit"]
    assert isinstance(rows, list)
    for row in rows:
        assert set(row) == {"code", "kind", "max_simultaneous", "real_teachers", "deficit"}


def test_portfolio_integration_mini_paquet(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"

    result = pipeline.solve_and_export(
        out_csv=out,
        paquet=FIXTURE,
        max_time_s=20,
        strategy="portfolio",
        portfolio=PortfolioConfig(seed=0, size=2, top_k=1, deterministic=True),
    )

    assert result.ok, result.summary
    assert out.is_file()
    assert any(r.startswith("audit:") for r in result.stage_reports)


def _partial_phase2(count: int) -> Phase2Result:
    ids = tuple(f"HIDDEN-ID-{i}" for i in range(count))
    return Phase2Result(True, [], "FEASIBLE", f"phase2 partial unassigned={count}", True, unassigned=ids)


def test_portfolio_prefers_complete_candidate_over_partial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    first = _partida_map(data, status="OPTIMAL")
    second = _partida_map(data, status="GREEDY_FALLBACK")
    phase2 = _Phase2Script([_partial_phase2(3), _ok_phase2()])
    _install(monkeypatch, data, _portfolio_result(first, (first, second)), phase2)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert result.ok, result.summary
    assert len(phase2.calls) == 2
    assert "phase1=GREEDY_FALLBACK" in result.summary
    assert "partial" not in result.summary


def test_portfolio_exports_best_partial_when_none_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    first = _partida_map(data, status="OPTIMAL")
    second = _partida_map(data, status="GREEDY_FALLBACK")
    phase2 = _Phase2Script([_partial_phase2(3), _partial_phase2(1)])
    _install(monkeypatch, data, _portfolio_result(first, (first, second)), phase2)
    out = tmp_path / "o.csv"
    json_out = tmp_path / "o.json"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio", json_out=json_out)

    assert not result.ok
    assert out.is_file()
    assert "partial: unassigned_rooms=1" in result.summary
    assert "phase1=GREEDY_FALLBACK" in result.summary
    text = json_out.read_text(encoding="utf-8")
    assert json.loads(text)["metrics"]["unassigned_rooms"] == 1
    assert "HIDDEN-ID" not in text


def _blocked(codes: tuple[str, ...]) -> PortfolioResult:
    best = Phase1Result(False, {}, {}, "INFEASIBLE_DATA", "precheck blocking: x")
    return PortfolioResult(
        best=best, ranked=(), candidates=(), n_effective=0, stages=("precheck:blocking",), blocking_codes=codes
    )


def test_precheck_single_day_overload_runs_r4_and_exports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_R4": "cpsat"}, steps=("RELAXED_R4",))
    phase2 = _Phase2Script([_ok_phase2()])
    _install(monkeypatch, data, _blocked(("SINGLE_DAY_OVERLOAD",)), phase2)
    _install_ladder(monkeypatch, ladder)
    out = tmp_path / "o.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    assert result.ok, result.summary
    assert out.is_file()
    assert "phase1=RELAXED_R4" in result.summary
    assert len(ladder.cpsat_calls) == 1
    assert ladder.cpsat_calls[0]["rules"] is None and ladder.cpsat_calls[0]["soft_overlap"] is True
    assert "relax: from precheck SINGLE_DAY_OVERLOAD" in result.stage_reports
    assert [r for r in result.stage_reports if r.startswith("relax:RELAXED")] == ["relax:RELAXED_R4 OPTIMAL"]
    assert len(phase2.calls) == 1


def test_precheck_siblings_only_starts_ladder_at_d7(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_D7": "cpsat"})
    _install(monkeypatch, data, _blocked(("SIBLINGS_EXCEED_DAYS",)), _Phase2Script([_ok_phase2()]))
    _install_ladder(monkeypatch, ladder)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert result.ok, result.summary
    assert "phase1=RELAXED_D7" in result.summary
    assert ladder.cpsat_calls[0]["rules"] == _D7_OFF
    assert "relax: from precheck SIBLINGS_EXCEED_DAYS" in result.stage_reports


def test_precheck_both_relaxable_codes_start_at_r4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {"RELAXED_R4": "cpsat"}, steps=("RELAXED_R4",))
    codes = ("SIBLINGS_EXCEED_DAYS", "SINGLE_DAY_OVERLOAD")
    _install(monkeypatch, data, _blocked(codes), _Phase2Script([_ok_phase2()]))
    _install_ladder(monkeypatch, ladder)

    result = pipeline.solve_and_export(out_csv=tmp_path / "o.csv", max_time_s=20, strategy="portfolio")

    assert result.ok, result.summary
    assert len(ladder.cpsat_calls) == 1 and ladder.cpsat_calls[0]["soft_overlap"] is True
    assert "relax: from precheck SIBLINGS_EXCEED_DAYS, SINGLE_DAY_OVERLOAD" in result.stage_reports


def test_precheck_relax_failure_reports_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData
) -> None:
    ladder = _Ladder(data, {}, steps=("RELAXED_R4",))
    _install(monkeypatch, data, _blocked(("SINGLE_DAY_OVERLOAD",)), _Phase2Script([]))
    _install_ladder(monkeypatch, ladder)
    out = tmp_path / "o.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    assert not result.ok
    assert "INFEASIBLE_DATA" in result.summary and "relax: RELAXED_R4=INFEASIBLE" in result.summary
    assert not out.exists()


@pytest.mark.parametrize(
    "codes",
    [
        ("EMPTY_DOMAIN",),
        ("EMPTY_DOMAIN", "SINGLE_DAY_OVERLOAD"),
        ("HETEROGENEOUS_ACTIVITY",),
        ("SHARED_NO_COMMON_SLOT", "SIBLINGS_EXCEED_DAYS"),
        (),
    ],
)
def test_precheck_other_blocking_codes_still_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data: TimetableData, codes: tuple[str, ...]
) -> None:
    ladder = _Ladder(data, {"RELAXED_R4": "cpsat"})
    phase2 = _Phase2Script([_ok_phase2()])
    _install(monkeypatch, data, _blocked(codes), phase2)
    _install_ladder(monkeypatch, ladder)
    out = tmp_path / "o.csv"

    result = pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    assert not result.ok
    assert "INFEASIBLE_DATA" in result.summary
    assert ladder.cpsat_calls == [] and ladder.greedy_calls == [] and phase2.calls == []
    assert not any(r.startswith("relax") for r in result.stage_reports)
    assert not out.exists()


def test_portfolio_writes_online_sessions_as_online(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    for source in FIXTURE.iterdir():
        text = source.read_text(encoding="utf-8")
        if source.name == "sessions.csv":
            text = text.replace(",A1,", ",A0826,")
        (paquet / source.name).write_text(text, encoding="utf-8")
    loaded = CsvTimetableSource(paquet).load()
    best = _partida_map(loaded)
    assignments = [
        Assignment(s.id, s.day, s.start_min, "Q1/1003" if s.activity_id == "A0826" else "Q1/1011")
        for s in loaded.sessions.values()
    ]
    _install(
        monkeypatch,
        loaded,
        _portfolio_result(best, (best,)),
        _Phase2Script([Phase2Result(True, assignments, "OPTIMAL", "ok")]),
    )
    out = tmp_path / "o.csv"

    pipeline.solve_and_export(out_csv=out, max_time_s=20, strategy="portfolio")

    rows = dict(line.split(",", 1) for line in out.read_text(encoding="utf-8").splitlines()[1:])
    assert rows["S00001"].endswith(",Q1/1003") and rows["S00002"].endswith(",Q1/1003")
    assert rows["S00003"].endswith(",Q1/1011")
