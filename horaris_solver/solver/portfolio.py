"""Portfolio strategy for Phase 1: GRASP greedy pool, validation, scoring and a hinted CP-SAT chain.

Every candidate is re-checked with ``validate_phase1``; invalid ones are discarded and never used as hints.
All solver calls are capped by both their stage ``Deadline`` and one global deadline (minus a reserve for
phase 2), so neither the stage budgets nor the total budget are exceeded by any solver call.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from horaris_solver.domain.models import TimetableData
from horaris_solver.solver.budget import Deadline, PortfolioBudget, next_cpsat_slice
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import Phase1Result, solve_phase1
from horaris_solver.solver.precheck import PrecheckReport, run_precheck
from horaris_solver.solver.rules import Phase1Rules
from horaris_solver.solver.score import Score, score_phase1
from horaris_solver.solver.validate import validate_phase1
from horaris_solver.solver.violations import Violation

MAX_SEED = 2**31 - 1
MAX_SIZE = 64
MAX_TOP_K = 8
MIN_CALL_S = 1.0


@dataclass(frozen=True)
class PortfolioConfig:
    seed: int = 0
    size: int = 16
    top_k: int = 3
    deterministic: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.seed <= MAX_SEED:
            raise ValueError(f"seed must be in [0, {MAX_SEED}], got {self.seed}")
        if not 1 <= self.size <= MAX_SIZE:
            raise ValueError(f"size must be in [1, {MAX_SIZE}], got {self.size}")
        if not 1 <= self.top_k <= min(MAX_TOP_K, self.size):
            raise ValueError(f"top_k must be in [1, min({MAX_TOP_K}, size={self.size})], got {self.top_k}")


@dataclass(frozen=True)
class Candidate:
    index: int
    seed: int  # candidate 0 is the deterministic greedy and ignores it
    result: Phase1Result
    score: Score
    violations: tuple[Violation, ...]

    @property
    def valid(self) -> bool:
        return self.result.ok and not self.violations


@dataclass(frozen=True)
class PortfolioResult:
    best: Phase1Result
    ranked: tuple[Phase1Result, ...]
    candidates: tuple[Candidate, ...]
    n_effective: int
    stages: tuple[str, ...]


@dataclass(frozen=True)
class _Accepted:
    result: Phase1Result
    score: Score


@dataclass(frozen=True)
class _Window:
    """The global deadline shared by every stage, minus the time reserved for what runs after the portfolio."""

    deadline: Deadline
    reserve_s: float

    def remaining(self) -> float:
        return max(0.0, self.deadline.remaining() - self.reserve_s)

    def available(self, stage: Deadline) -> float:
        return min(stage.remaining(), self.remaining())


def _violation_summary(violations: Iterable[Violation]) -> str:
    counts = Counter(v.rule for v in violations)
    return ",".join(f"{rule}={n}" for rule, n in sorted(counts.items()))


def _precheck_summary(report: PrecheckReport) -> str:
    counts = Counter(issue.code for issue in report.issues if issue.blocking)
    return ", ".join(f"{code}={n}" for code, n in sorted(counts.items()))


def _log_candidate(log_path: Path, candidate: Candidate, elapsed_s: float) -> None:
    score = candidate.score
    line = {
        "index": candidate.index,
        "seed": candidate.seed,
        "status": candidate.result.status,
        "ok": candidate.result.ok,
        "n_violations": len(candidate.violations),
        "score_hard": score.hard,
        "score_unplaced": score.unplaced,
        "score_soft": score.soft,
        "hores_mortes_min": score.hores_mortes_min,
        "canvis_franja": score.canvis_franja,
        "n_unplaced": len(candidate.result.unplaced),
        "elapsed_s": round(elapsed_s, 3),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")


def _evaluate(data: TimetableData, index: int, seed: int, result: Phase1Result, rules: Phase1Rules | None) -> Candidate:
    violations = tuple(validate_phase1(data, result, rules))
    score = score_phase1(data, result, hard_violations=len(violations))
    return Candidate(index=index, seed=seed, result=result, score=score, violations=violations)


def _candidate_stage(candidate: Candidate) -> str:
    prefix = f"greedy[{candidate.index}]"
    if candidate.valid:
        return f"{prefix}:valid"
    if not candidate.result.ok:
        return f"{prefix}:discard status={candidate.result.status} unplaced={candidate.score.unplaced}"
    return f"{prefix}:discard violations {_violation_summary(candidate.violations)}"


def _pool_stop(index: int, config: PortfolioConfig, greedy: Deadline, window: _Window) -> str | None:
    """Why the pool must stop before candidate ``index``; candidate 0 always runs."""
    if index == 0:
        return None
    if window.remaining() < MIN_CALL_S:
        return f"greedy:global-deadline n_effective={index}/{config.size}"
    if not config.deterministic and greedy.remaining() < MIN_CALL_S:
        return f"greedy:deadline n_effective={index}/{config.size}"
    return None


def _run_pool(
    data: TimetableData,
    config: PortfolioConfig,
    budget: PortfolioBudget,
    rules: Phase1Rules | None,
    log_path: Path | None,
    clock: Callable[[], float],
    window: _Window,
    stages: list[str],
) -> list[Candidate]:
    """Run the GRASP pool; ``deterministic`` runs exactly ``size`` candidates unless the global deadline hits."""
    greedy = Deadline(budget.greedy_s, clock)
    candidates: list[Candidate] = []
    for index in range(config.size):
        stop = _pool_stop(index, config, greedy, window)
        if stop is not None:
            stages.append(stop)
            break
        started = clock()
        seed = config.seed + index
        repair_s = min(budget.repair_s, window.remaining() if config.deterministic else window.available(greedy))
        if index == 0:
            result = solve_phase1_greedy(data, rules=rules, repair_time_s=repair_s, deterministic=config.deterministic)
        else:
            result = solve_phase1_greedy(
                data, seed=seed, rules=rules, repair_time_s=repair_s, deterministic=config.deterministic
            )
        candidate = _evaluate(data, index, seed, result, rules)
        candidates.append(candidate)
        stages.append(_candidate_stage(candidate))
        if log_path is not None:
            _log_candidate(log_path, candidate, clock() - started)
    return candidates


def _try_cpsat(
    data: TimetableData,
    *,
    label: str,
    hints: Phase1Result | None,
    max_time_s: float,
    config: PortfolioConfig,
    rules: Phase1Rules | None,
    stages: list[str],
) -> tuple[str, _Accepted | None]:
    result = solve_phase1(
        data,
        max_time_s=max_time_s,
        hints=hints,
        stop_after_first_feasible=False,
        random_seed=config.seed,
        rules=rules,
        deterministic=config.deterministic,
    )
    if not result.ok:
        stages.append(f"{label}:{result.status}")
        return result.status, None
    violations = validate_phase1(data, result, rules)
    if violations:
        stages.append(f"{label}:{result.status} invalid {_violation_summary(violations)}")
        return f"{result.status}_INVALID", None
    stages.append(f"{label}:{result.status} accepted")
    return result.status, _Accepted(result, score_phase1(data, result, hard_violations=0))


def _run_cpsat_chain(
    data: TimetableData,
    top: list[Candidate],
    config: PortfolioConfig,
    budget: PortfolioBudget,
    rules: Phase1Rules | None,
    clock: Callable[[], float],
    window: _Window,
    stages: list[str],
) -> tuple[str, _Accepted | None]:
    deadline = Deadline(budget.cpsat_s, clock)
    status = "SKIPPED"
    if not top:
        if window.available(deadline) < MIN_CALL_S:
            stages.append("cpsat[nohint]:skipped no time")
            return status, None
        return _try_cpsat(
            data,
            label="cpsat[nohint]",
            hints=None,
            max_time_s=window.available(deadline),
            config=config,
            rules=rules,
            stages=stages,
        )
    for attempt, candidate in enumerate(top, start=1):
        available = window.available(deadline)
        if available < MIN_CALL_S:
            stages.append(f"cpsat[{attempt}]:skipped no time")
            break
        wanted = budget.first_cpsat_s if attempt == 1 else next_cpsat_slice(available, len(top) - attempt + 1)
        status, accepted = _try_cpsat(
            data,
            label=f"cpsat[{attempt}] hint=greedy[{candidate.index}]",
            hints=candidate.result,
            max_time_s=min(wanted, available),
            config=config,
            rules=rules,
            stages=stages,
        )
        if accepted is not None:
            return status, accepted
    return status, None


def _map_key(result: Phase1Result) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, int], ...]]:
    return tuple(sorted(result.activity_day.items())), tuple(sorted(result.activity_start.items()))


def _rank(entries: list[tuple[Score, int, Phase1Result]]) -> tuple[Phase1Result, ...]:
    seen: set[tuple[tuple[tuple[str, str], ...], tuple[tuple[str, int], ...]]] = set()
    ranked: list[Phase1Result] = []
    for _, _, result in sorted(entries, key=lambda e: (e[0], e[1])):
        key = _map_key(result)
        if key not in seen:
            seen.add(key)
            ranked.append(result)
    return tuple(ranked)


def _unplaced_ids(data: TimetableData, result: Phase1Result) -> tuple[str, ...]:
    if result.unplaced:
        return result.unplaced
    return tuple(aid for aid in data.activities if aid not in result.activity_day or aid not in result.activity_start)


def _infeasible(data: TimetableData, candidates: list[Candidate], cpsat_status: str) -> Phase1Result:
    partial = min(candidates, key=lambda c: (c.score, c.index))
    unplaced = _unplaced_ids(data, partial.result)
    return Phase1Result(
        False,
        dict(partial.result.activity_day),
        dict(partial.result.activity_start),
        "INFEASIBLE",
        f"portfolio found no valid schedule; cpsat {cpsat_status}; best greedy[{partial.index}] "
        f"left {len(unplaced)} unplaced",
        unplaced=unplaced,
    )


def _check_log_path(log_path: Path | None) -> None:
    if log_path is not None and not log_path.parent.is_dir():
        raise ValueError("log_path parent directory does not exist")


def run_portfolio(
    data: TimetableData,
    *,
    config: PortfolioConfig,
    budget: PortfolioBudget,
    rules: Phase1Rules | None = None,
    log_path: Path | None = None,
    clock: Callable[[], float] = time.monotonic,
    deadline: Deadline | None = None,
) -> PortfolioResult:
    """Run precheck, the greedy pool and the hinted CP-SAT chain; return the best valid Phase 1 map.

    ``deadline`` is the caller's global deadline: every call is capped at its remaining time minus
    ``budget.phase2_s``. Without it the portfolio gets ``budget.greedy_s + budget.cpsat_s`` in total.
    """
    _check_log_path(log_path)
    if deadline is None:
        window = _Window(Deadline(budget.greedy_s + budget.cpsat_s, clock), 0.0)
    else:
        window = _Window(deadline, budget.phase2_s)
    precheck = run_precheck(data, rules)
    if precheck.blocking:
        best = Phase1Result(False, {}, {}, "INFEASIBLE_DATA", f"precheck blocking: {_precheck_summary(precheck)}")
        return PortfolioResult(best=best, ranked=(), candidates=(), n_effective=0, stages=("precheck:blocking",))

    stages: list[str] = ["precheck:ok"]
    candidates = _run_pool(data, config, budget, rules, log_path, clock, window, stages)
    valid = sorted((c for c in candidates if c.valid), key=lambda c: (c.score, c.index))
    top = valid[: config.top_k]
    stages.append(f"greedy:top_k={[c.index for c in top]}")

    cpsat_status, accepted = _run_cpsat_chain(data, top, config, budget, rules, clock, window, stages)

    if accepted is None and not top:
        stages.append("best:none")
        return PortfolioResult(
            best=_infeasible(data, candidates, cpsat_status),
            ranked=(),
            candidates=tuple(candidates),
            n_effective=len(candidates),
            stages=tuple(stages),
        )

    entries: list[tuple[Score, int, Phase1Result]] = []
    if accepted is not None:
        entries.append((accepted.score, -1, accepted.result))
    greedy_best: Phase1Result | None = None
    if top and (accepted is None or top[0].score < accepted.score):
        winner = top[0]
        detail = "worse score" if accepted is not None else "no valid result"
        greedy_best = replace(
            winner.result,
            status="GREEDY_FALLBACK",
            message=f"greedy[{winner.index}] chosen; cpsat {cpsat_status} ({detail})",
        )
        stages.append(f"best:greedy[{winner.index}]")
    else:
        stages.append("best:cpsat")
    for candidate in top:
        result = greedy_best if greedy_best is not None and candidate is top[0] else candidate.result
        entries.append((candidate.score, candidate.index, result))

    ranked = _rank(entries)
    return PortfolioResult(
        best=ranked[0],
        ranked=ranked,
        candidates=tuple(candidates),
        n_effective=len(candidates),
        stages=tuple(stages),
    )
