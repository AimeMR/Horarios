from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import TimetableData
from horaris_solver.solver import portfolio
from horaris_solver.solver.budget import Deadline, PortfolioBudget, split_portfolio
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.portfolio import PortfolioConfig, run_portfolio
from horaris_solver.solver.precheck import PrecheckIssue, PrecheckReport
from horaris_solver.solver.rules import Phase1Rules
from horaris_solver.solver.score import Score
from horaris_solver.solver.validate import validate_phase1
from horaris_solver.solver.violations import Violation

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
BUDGET = PortfolioBudget(greedy_s=10.0, repair_s=2.5, cpsat_s=20.0, first_cpsat_s=12.0, phase2_s=10.0)
BAD = "bad"  # message marker: the fake validator reports a D4 clash for these results


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def greedy_result(soft: int, *, ok: bool = True, bad: bool = False, start: int | None = None) -> Phase1Result:
    unplaced = () if ok else ("A2",)
    return Phase1Result(
        ok,
        {"A1": "L"},
        {"A1": start if start is not None else 540 + soft},
        "GREEDY" if ok else "GREEDY_PARTIAL",
        BAD if bad else "",
        objective=soft,
        unplaced=unplaced,
    )


@dataclass
class Harness:
    """Monkeypatched solver stack: scripted greedy/CP-SAT outputs, a fake clock and call records."""

    greedy: list[Phase1Result]
    cpsat: list[Phase1Result] = field(default_factory=list)
    greedy_cost_s: float = 0.0
    cpsat_cost_s: float = 0.0
    clock: FakeClock = field(default_factory=FakeClock)
    greedy_calls: list[dict[str, Any]] = field(default_factory=list)
    cpsat_calls: list[dict[str, Any]] = field(default_factory=list)
    blocking: bool = False

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(portfolio, "solve_phase1_greedy", self._greedy)
        monkeypatch.setattr(portfolio, "solve_phase1", self._cpsat)
        monkeypatch.setattr(portfolio, "validate_phase1", self._validate)
        monkeypatch.setattr(portfolio, "score_phase1", self._score)
        monkeypatch.setattr(portfolio, "run_precheck", self._precheck)

    def _greedy(self, data: TimetableData, **kwargs: Any) -> Phase1Result:
        self.greedy_calls.append({**kwargs, "now": self.clock.now})
        self.clock.now += self.greedy_cost_s
        return self.greedy[len(self.greedy_calls) - 1]

    def _cpsat(self, data: TimetableData, **kwargs: Any) -> Phase1Result:
        self.cpsat_calls.append({**kwargs, "now": self.clock.now})
        self.clock.now += min(self.cpsat_cost_s, kwargs["max_time_s"])
        return self.cpsat[len(self.cpsat_calls) - 1]

    @staticmethod
    def _validate(data: TimetableData, result: Phase1Result, rules: Phase1Rules | None = None) -> list[Violation]:
        return [Violation("D4-CLASH", ("A1", "A2"), "teacher X")] if result.message == BAD else []

    @staticmethod
    def _score(data: TimetableData, result: Phase1Result, *, hard_violations: int = 0) -> Score:
        return Score(hard_violations, len(result.unplaced), result.objective, 0, 0)

    def _precheck(self, data: TimetableData, rules: Phase1Rules | None = None) -> PrecheckReport:
        issues = (
            (
                PrecheckIssue("EMPTY_DOMAIN", ("A1",), "no slots", True),
                PrecheckIssue("EMPTY_DOMAIN", ("A2",), "x", True),
            )
            if self.blocking
            else ()
        )
        return PrecheckReport(issues)


@pytest.fixture(scope="module")
def data() -> TimetableData:
    return CsvTimetableSource(FIXTURE).load()


def cpsat_ok(soft: int, status: str = "FEASIBLE") -> Phase1Result:
    return Phase1Result(True, {"A1": "M"}, {"A1": 600 + soft}, status, "", objective=soft)


def cpsat_fail(status: str = "UNKNOWN") -> Phase1Result:
    return Phase1Result(False, {}, {}, status, "")


def run(h: Harness, data: TimetableData, monkeypatch: pytest.MonkeyPatch, **config: Any) -> portfolio.PortfolioResult:
    h.install(monkeypatch)
    return run_portfolio(data, config=PortfolioConfig(**config), budget=BUDGET, clock=h.clock)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1},
        {"seed": 2**31},
        {"size": 0},
        {"size": 65},
        {"top_k": 0},
        {"size": 2, "top_k": 3},
        {"size": 16, "top_k": 9},
    ],
)
def test_config_rejects_out_of_range(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        PortfolioConfig(**kwargs)


def test_config_accepts_bounds() -> None:
    PortfolioConfig(seed=2**31 - 1, size=64, top_k=8)
    PortfolioConfig(seed=0, size=1, top_k=1)


def test_blocking_precheck_short_circuits(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(1)], blocking=True)
    out = run(h, data, monkeypatch, size=1, top_k=1)
    assert out.best.status == "INFEASIBLE_DATA"
    assert not out.best.ok
    assert "EMPTY_DOMAIN=2" in out.best.message
    assert (out.ranked, out.candidates, out.n_effective, out.stages) == ((), (), 0, ("precheck:blocking",))
    assert h.greedy_calls == [] and h.cpsat_calls == []


def test_seeds_candidate_zero_deterministic(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(i) for i in range(3)], cpsat=[cpsat_ok(0)])
    run(h, data, monkeypatch, seed=7, size=3, top_k=1)
    assert "seed" not in h.greedy_calls[0]
    assert [c["seed"] for c in h.greedy_calls[1:]] == [8, 9]
    assert all(c["repair_time_s"] == BUDGET.repair_s for c in h.greedy_calls)


def test_invalid_candidates_discarded_and_never_hints(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    good = greedy_result(50)
    h = Harness(
        greedy=[greedy_result(1, bad=True), greedy_result(2, ok=False), good],
        cpsat=[cpsat_fail(), cpsat_fail()],
    )
    out = run(h, data, monkeypatch, size=3, top_k=3)
    assert [c["hints"] for c in h.cpsat_calls] == [good]
    assert out.ranked == (out.best,)
    assert any(s.startswith("greedy[0]:discard violations D4-CLASH=1") for s in out.stages)
    assert any(s.startswith("greedy[1]:discard status=GREEDY_PARTIAL") for s in out.stages)


def test_top_k_ordered_by_score_then_index(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(
        greedy=[greedy_result(30), greedy_result(10, start=700), greedy_result(20), greedy_result(10, start=701)],
        cpsat=[cpsat_fail(), cpsat_fail(), cpsat_fail()],
    )
    out = run(h, data, monkeypatch, size=4, top_k=3)
    hints = [c["hints"] for c in h.cpsat_calls]
    assert hints == [h.greedy[1], h.greedy[3], h.greedy[2]]
    assert "greedy:top_k=[1, 3, 2]" in out.stages
    assert out.ranked[1:] == (h.greedy[3], h.greedy[2])


def test_cpsat_failure_falls_to_next_hint(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    accepted = cpsat_ok(1, "OPTIMAL")
    h = Harness(greedy=[greedy_result(10), greedy_result(20)], cpsat=[cpsat_fail("INFEASIBLE"), accepted])
    out = run(h, data, monkeypatch, size=2, top_k=2, seed=5, deterministic=True)
    assert [c["hints"] for c in h.cpsat_calls] == [h.greedy[0], h.greedy[1]]
    assert out.best is accepted
    assert out.best.status == "OPTIMAL"
    assert out.ranked == (accepted, h.greedy[0], h.greedy[1])
    first = h.cpsat_calls[0]
    assert first["max_time_s"] == BUDGET.first_cpsat_s
    assert first["random_seed"] == 5 and first["deterministic"] is True
    assert first["stop_after_first_feasible"] is False


def test_invalid_cpsat_result_is_not_accepted(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = Phase1Result(True, {"A1": "M"}, {"A1": 600}, "FEASIBLE", BAD, objective=0)
    h = Harness(greedy=[greedy_result(10)], cpsat=[invalid])
    out = run(h, data, monkeypatch, size=1, top_k=1)
    assert out.best.status == "GREEDY_FALLBACK"
    assert "FEASIBLE_INVALID" in out.best.message


def test_all_cpsat_fail_gives_greedy_fallback(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(20), greedy_result(10)], cpsat=[cpsat_fail(), cpsat_fail()])
    out = run(h, data, monkeypatch, size=2, top_k=2)
    assert out.best.ok
    assert out.best.status == "GREEDY_FALLBACK"
    assert "UNKNOWN" in out.best.message
    assert out.best.activity_start == h.greedy[1].activity_start
    assert out.ranked == (out.best, h.greedy[0])


def test_greedy_beats_worse_cpsat(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(5)], cpsat=[cpsat_ok(9)])
    out = run(h, data, monkeypatch, size=1, top_k=1)
    assert out.best.status == "GREEDY_FALLBACK"
    assert out.ranked == (out.best, h.cpsat[0])


def test_nothing_valid_is_infeasible_with_unplaced(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(1, ok=False), greedy_result(2, bad=True)], cpsat=[cpsat_fail("INFEASIBLE")])
    out = run(h, data, monkeypatch, size=2, top_k=1)
    assert not out.best.ok
    assert out.best.status == "INFEASIBLE"
    assert out.best.unplaced == ("A2",)
    assert "INFEASIBLE" in out.best.message and "1 unplaced" in out.best.message
    assert out.ranked == ()


def test_no_valid_greedy_runs_one_hintless_cpsat(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    accepted = cpsat_ok(3)
    h = Harness(greedy=[greedy_result(1, ok=False), greedy_result(2, ok=False)], cpsat=[accepted], greedy_cost_s=1.0)
    out = run(h, data, monkeypatch, size=2, top_k=2)
    assert len(h.cpsat_calls) == 1
    assert h.cpsat_calls[0]["hints"] is None
    assert h.cpsat_calls[0]["max_time_s"] == BUDGET.cpsat_s
    assert out.best is accepted
    assert out.ranked == (accepted,)


def test_greedy_deadline_stops_pool_but_runs_candidate_zero(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(greedy=[greedy_result(i) for i in range(8)], cpsat=[cpsat_ok(0)], greedy_cost_s=4.0)
    out = run(h, data, monkeypatch, size=8, top_k=1)
    assert out.n_effective == 3  # starts at t=0, 4, 8; at t=12 the 10 s greedy budget is spent
    assert len(out.candidates) == 3
    assert any(s.startswith("greedy:deadline n_effective=3/8") for s in out.stages)
    assert h.greedy_calls[2]["repair_time_s"] == pytest.approx(2.0)


def test_non_deterministic_pool_passes_flag_and_stops_on_greedy_deadline(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(greedy=[greedy_result(i) for i in range(8)], cpsat=[cpsat_ok(0)], greedy_cost_s=4.0)
    out = run(h, data, monkeypatch, size=8, top_k=1)
    assert out.n_effective < 8
    assert all(c["deterministic"] is False for c in h.greedy_calls)


def test_deterministic_runs_exactly_size_past_greedy_deadline(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(greedy=[greedy_result(i) for i in range(6)], cpsat=[cpsat_ok(0)], greedy_cost_s=4.0)
    out = run(h, data, monkeypatch, size=6, top_k=1, seed=3, deterministic=True)
    assert out.n_effective == 6  # 24 s of greedy work although greedy_s is 10 s
    assert not any(s.startswith("greedy:deadline") or s.startswith("greedy:global") for s in out.stages)
    assert all(c["deterministic"] is True for c in h.greedy_calls)
    assert "seed" not in h.greedy_calls[0]
    assert [c["seed"] for c in h.greedy_calls[1:]] == [4, 5, 6, 7, 8]
    assert all(c["repair_time_s"] == BUDGET.repair_s for c in h.greedy_calls)


def test_deterministic_pool_stops_at_global_deadline(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(i) for i in range(8)], cpsat=[cpsat_ok(0)], greedy_cost_s=2.0)
    h.install(monkeypatch)
    deadline = Deadline(BUDGET.phase2_s + 5.0, h.clock)  # 5 s left for the portfolio after the phase 2 reserve
    out = run_portfolio(
        data,
        config=PortfolioConfig(size=8, top_k=1, deterministic=True),
        budget=BUDGET,
        clock=h.clock,
        deadline=deadline,
    )
    assert out.n_effective == 3  # starts at t=0, 2, 4; at t=6 nothing is left
    assert "greedy:global-deadline n_effective=3/8" in out.stages
    assert h.cpsat_calls == []
    assert "cpsat[1]:skipped no time" in out.stages
    assert deadline.remaining() >= BUDGET.phase2_s - 1.0


@pytest.mark.parametrize("deterministic", [False, True])
def test_global_deadline_caps_every_call_and_keeps_phase2_reserve(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch, deterministic: bool
) -> None:
    h = Harness(
        greedy=[greedy_result(i) for i in range(2)],
        cpsat=[cpsat_fail(), cpsat_fail()],
        greedy_cost_s=9.0,
        cpsat_cost_s=100.0,
    )
    h.install(monkeypatch)
    total = BUDGET.greedy_s + BUDGET.cpsat_s + BUDGET.phase2_s
    out = run_portfolio(
        data,
        config=PortfolioConfig(size=2, top_k=2, deterministic=deterministic),
        budget=BUDGET,
        clock=h.clock,
        deadline=Deadline(total, h.clock),
    )
    for call in h.greedy_calls:
        assert call["repair_time_s"] <= total - BUDGET.phase2_s - call["now"] + 1e-9
    for call in h.cpsat_calls:
        assert call["max_time_s"] <= total - BUDGET.phase2_s - call["now"] + 1e-9
    assert [c["max_time_s"] for c in h.cpsat_calls] == [pytest.approx(12.0)]  # greedy overran into CP-SAT time
    assert h.clock.now <= BUDGET.greedy_s + BUDGET.cpsat_s + 1e-9
    assert out.best.status == "GREEDY_FALLBACK"


def test_without_global_deadline_total_stays_within_greedy_plus_cpsat(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(
        greedy=[greedy_result(i) for i in range(2)],
        cpsat=[cpsat_fail(), cpsat_fail()],
        greedy_cost_s=9.0,
        cpsat_cost_s=100.0,
    )
    run(h, data, monkeypatch, size=2, top_k=2)
    assert h.clock.now <= BUDGET.greedy_s + BUDGET.cpsat_s + 1e-9
    assert [c["max_time_s"] for c in h.cpsat_calls] == [pytest.approx(12.0)]


def test_candidate_zero_runs_even_with_no_greedy_budget(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(1), greedy_result(2)], cpsat=[cpsat_ok(0)])
    h.install(monkeypatch)
    tiny = PortfolioBudget(greedy_s=0.5, repair_s=0.1, cpsat_s=5.0, first_cpsat_s=3.0, phase2_s=1.0)
    out = run_portfolio(data, config=PortfolioConfig(size=2, top_k=1), budget=tiny, clock=h.clock)
    assert out.n_effective == 1


def test_every_cpsat_call_fits_remaining_budget(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(
        greedy=[greedy_result(i) for i in range(3)],
        cpsat=[cpsat_fail(), cpsat_fail(), cpsat_fail()],
        greedy_cost_s=1.0,
        cpsat_cost_s=100.0,
    )
    out = run(h, data, monkeypatch, size=3, top_k=3)
    cpsat_start = h.cpsat_calls[0]["now"]
    for call in h.cpsat_calls:
        assert call["max_time_s"] <= BUDGET.cpsat_s - (call["now"] - cpsat_start) + 1e-9
    assert [c["max_time_s"] for c in h.cpsat_calls] == [pytest.approx(12.0), pytest.approx(4.0), pytest.approx(4.0)]
    assert h.clock.now - cpsat_start <= BUDGET.cpsat_s
    assert out.best.status == "GREEDY_FALLBACK"


def test_cpsat_skipped_when_under_one_second(data: TimetableData, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(greedy=[greedy_result(1), greedy_result(2)], cpsat=[cpsat_fail()], cpsat_cost_s=100.0)
    h.install(monkeypatch)
    budget = PortfolioBudget(greedy_s=5.0, repair_s=1.0, cpsat_s=5.0, first_cpsat_s=5.0, phase2_s=1.0)
    out = run_portfolio(data, config=PortfolioConfig(size=2, top_k=2), budget=budget, clock=h.clock)
    assert len(h.cpsat_calls) == 1
    assert "cpsat[2]:skipped no time" in out.stages
    assert out.best.status == "GREEDY_FALLBACK"


def test_jsonl_log_has_no_ids_or_teacher_names(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "portfolio.jsonl"
    h = Harness(greedy=[greedy_result(1, bad=True), greedy_result(2)], cpsat=[cpsat_ok(0)])
    h.install(monkeypatch)
    run_portfolio(data, config=PortfolioConfig(size=2, top_k=1), budget=BUDGET, clock=h.clock, log_path=log)
    text = log.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in text.splitlines()]
    assert [line["index"] for line in lines] == [0, 1]
    assert lines[0]["n_violations"] == 1 and lines[0]["ok"] is True
    assert {"seed", "status", "score_hard", "score_unplaced", "score_soft", "n_unplaced", "elapsed_s"} <= set(lines[0])
    assert "A1" not in text and "A2" not in text and "teacher" not in text


def test_log_path_requires_existing_parent(
    data: TimetableData, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    h = Harness(greedy=[greedy_result(1)], cpsat=[cpsat_ok(0)])
    h.install(monkeypatch)
    with pytest.raises(ValueError):
        run_portfolio(
            data, config=PortfolioConfig(size=1, top_k=1), budget=BUDGET, clock=h.clock, log_path=tmp_path / "x" / "l"
        )
    assert h.greedy_calls == []
    assert not (tmp_path / "x").exists()


def test_mini_paquet_real_solvers(data: TimetableData) -> None:
    rules = Phase1Rules()
    out = run_portfolio(
        data,
        config=PortfolioConfig(seed=0, size=3, top_k=2, deterministic=True),
        budget=split_portfolio(20.0),
        rules=rules,
    )
    assert out.best.ok, out.best.message
    assert validate_phase1(data, out.best, rules) == []
    assert 1 <= out.n_effective <= 3
    assert out.ranked and out.ranked[0] is out.best
