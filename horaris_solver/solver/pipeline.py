"""Orchestrate load → phase1 (CP-SAT / greedy) → phase2 → export."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.adapters.sqlite_loader import SqliteTimetableSource
from horaris_solver.audit.cohort_clashes import find_cohort_clashes
from horaris_solver.audit.overlaps import find_room_overlaps
from horaris_solver.domain.filters import parse_cursos, parse_titulacions
from horaris_solver.domain.models import Assignment, TimetableData
from horaris_solver.export.csv_proposta import write_proposta_csv
from horaris_solver.export.json_rich import write_rich_json
from horaris_solver.solver.budget import PORTFOLIO_MIN_TOTAL_S, Deadline, split_hybrid, split_portfolio
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import (
    Phase1Result,
    expand_phase1_to_assignments,
    solve_phase1,
)
from horaris_solver.solver.phase2_rooms import Phase2Result, solve_phase2
from horaris_solver.solver.portfolio import PortfolioConfig, run_portfolio
from horaris_solver.solver.rules import Phase1Rules, pool_violations, sibling_violations
from horaris_solver.solver.score import score_phase1
from horaris_solver.solver.teacher_deficit import DeficitRow, compute_deficit, write_deficit_csv
from horaris_solver.solver.validate import validate_phase1

STRATEGIES = frozenset({"hybrid", "greedy", "cpsat", "portfolio"})
PORTFOLIO_RETRY_MIN_S = 5.0
MIN_STAGE_S = 1.0


def default_max_time_s() -> int:
    raw = os.environ.get("SOLVER_MAX_TIME_S", "300")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("SOLVER_MAX_TIME_S must be an integer") from exc
    if value < 1:
        raise ValueError("SOLVER_MAX_TIME_S must be >= 1")
    return value


@dataclass(frozen=True)
class SolveExportResult:
    ok: bool
    summary: str
    out_csv: Path
    r8_relaxed: bool = False
    stage_reports: tuple[str, ...] = ()


def _load_data(
    *,
    paquet: Path | None,
    db: Path | None,
    semestre: int | None,
    cursos: frozenset[str] | None = None,
    titulacions: frozenset[str] | None = None,
) -> TimetableData:
    if db is not None and paquet is not None:
        raise ValueError("pass either --db or --paquet, not both")
    if db is not None:
        return SqliteTimetableSource(db).load(semestre=semestre, cursos=cursos, titulacions=titulacions)
    if paquet is not None:
        return CsvTimetableSource(paquet).load(semestre=semestre, cursos=cursos, titulacions=titulacions)
    env_db = os.environ.get("HORARIS_DB", "").strip()
    if env_db:
        return SqliteTimetableSource(Path(env_db)).load(semestre=semestre, cursos=cursos, titulacions=titulacions)
    env_paquet = os.environ.get("HORARIS_PAQUET", "").strip()
    if env_paquet:
        return CsvTimetableSource(Path(env_paquet)).load(semestre=semestre, cursos=cursos, titulacions=titulacions)
    raise ValueError("provide --db, --paquet, or set HORARIS_DB / HORARIS_PAQUET")


def _run_phase1(
    data: TimetableData,
    *,
    strategy: str,
    max_time_s: float,
) -> Phase1Result:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(STRATEGIES)}")
    if strategy == "portfolio":
        raise ValueError("strategy 'portfolio' runs through solve_and_export")
    if strategy == "greedy":
        return solve_phase1_greedy(data)
    if strategy == "cpsat":
        return solve_phase1(data, max_time_s=max_time_s)
    # hybrid: greedy warm pack (hint only when it validates), then CP-SAT; if CP-SAT fails keep greedy when feasible
    greedy = solve_phase1_greedy(data)
    hints = None if validate_phase1(data, greedy) else greedy
    cpsat = solve_phase1(
        data,
        max_time_s=max_time_s,
        hints=hints,
        stop_after_first_feasible=True,
    )
    if cpsat.ok:
        return cpsat
    if greedy.ok:
        return Phase1Result(
            True,
            greedy.activity_day,
            greedy.activity_start,
            "GREEDY_FALLBACK",
            f"cpsat={cpsat.status}; {greedy.message}",
            objective=greedy.objective,
        )
    return Phase1Result(
        False,
        greedy.activity_day,
        greedy.activity_start,
        "INFEASIBLE",
        f"cpsat={cpsat.status}; greedy={greedy.message}",
        unplaced=greedy.unplaced,
    )


@dataclass(frozen=True)
class _Solved:
    """Outcome of phase 1 + phase 2 before export; ``failure`` set means there is nothing to export."""

    phase1: Phase1Result
    phase2: Phase2Result | None
    stage_reports: tuple[str, ...] = ()
    failure: str | None = None
    new_room_overlaps: int = 0
    new_cohort_clashes: int = 0
    extra_metrics: dict[str, Any] | None = None


def _solve_classic(data: TimetableData, *, strategy: str, budget: int) -> _Solved:
    phase1_budget, phase2_budget = split_hybrid(float(budget))
    phase1 = _run_phase1(data, strategy=strategy, max_time_s=phase1_budget)
    if not phase1.ok:
        return _Solved(phase1, None, failure=f"phase1 failed: {phase1.status} {phase1.message}")
    timed = expand_phase1_to_assignments(data, phase1)
    phase2 = solve_phase2(data, timed, max_time_s=phase2_budget, r8_soft_fallback=True)
    if not phase2.ok:
        return _Solved(phase1, phase2, failure=f"phase2 failed: {phase2.status} {phase2.message}")
    return _Solved(phase1, phase2)


_IssueKeys = tuple[set[frozenset[str]], set[frozenset[str]]]


def _issue_keys(data: TimetableData, assignments: list[Assignment] | None) -> _IssueKeys:
    """Session-id pairs in room overlaps and cohort clashes (``None`` audits partida)."""
    partida = assignments is None
    rooms = find_room_overlaps(data, assignments, use_partida=partida)
    cohorts = find_cohort_clashes(data, assignments, use_partida=partida)
    return (
        {frozenset((o.left_id, o.right_id)) for o in rooms},
        {frozenset((c.left_id, c.right_id)) for c in cohorts},
    )


@dataclass(frozen=True)
class _RelaxStep:
    """One rung of the phase-1 relaxation ladder (D7 is dropped on every rung)."""

    name: str
    rules: Phase1Rules | None
    soft_overlap: bool
    drops_d6: bool


RELAX_LADDER: tuple[_RelaxStep, ...] = (
    _RelaxStep("RELAXED_D7", Phase1Rules(same_kind_day=False, room_pools=True), False, False),
    _RelaxStep("RELAXED_D6_D7", None, False, True),
    _RelaxStep("RELAXED_R4", None, True, True),
)
RELAX_REPAIR_MAX_S = 45.0
# Blocking precheck codes the ladder can absorb, mapped to the first rung that relaxes them.
PRECHECK_RELAX_START: dict[str, str] = {
    "SIBLINGS_EXCEED_DAYS": "RELAXED_D7",
    "SINGLE_DAY_OVERLOAD": "RELAXED_R4",
}


def _precheck_relax_steps(codes: tuple[str, ...]) -> tuple[_RelaxStep, ...]:
    """Ladder rungs to try when the precheck blocked only on relaxable codes; empty means abort."""
    if not codes or not set(codes) <= PRECHECK_RELAX_START.keys():
        return ()
    names = [step.name for step in RELAX_LADDER]
    start = max(names.index(PRECHECK_RELAX_START[code]) for code in codes)
    return RELAX_LADDER[start:]


def _run_relax_step(
    data: TimetableData, step: _RelaxStep, *, slice_s: float, config: PortfolioConfig
) -> tuple[Phase1Result | None, str]:
    """Greedy warm start then CP-SAT under the step's rules; returns the accepted result (or None) and a status."""
    greedy = solve_phase1_greedy(data, rules=step.rules, repair_time_s=min(RELAX_REPAIR_MAX_S, slice_s / 4))
    greedy_valid = greedy.ok and not validate_phase1(data, greedy, step.rules)
    cpsat = solve_phase1(
        data,
        max_time_s=slice_s,
        hints=greedy if greedy_valid else None,
        rules=step.rules,
        soft_overlap=step.soft_overlap,
        random_seed=config.seed,
        deterministic=config.deterministic,
    )
    if cpsat.ok and (step.soft_overlap or not validate_phase1(data, cpsat, step.rules)):
        return replace(cpsat, status=step.name, message=f"{cpsat.status}: {cpsat.message}"), cpsat.status
    if greedy_valid:
        message = f"greedy; cpsat={cpsat.status}: {greedy.message}"
        return replace(greedy, status=step.name, message=message), f"{cpsat.status} greedy=ok"
    return None, cpsat.status


def _relax_ladder(
    data: TimetableData,
    *,
    deadline: Deadline,
    reserve_s: float,
    config: PortfolioConfig,
    stages: list[str],
    steps: tuple[_RelaxStep, ...] = RELAX_LADDER,
) -> tuple[Phase1Result | None, _RelaxStep | None, list[str]]:
    """Run the rungs in order, sharing the time left (minus the phase-2 reserve); first accepted rung wins."""
    outcomes: list[str] = []
    for index, step in enumerate(steps):
        slice_s = deadline.cap((deadline.remaining() - reserve_s) / (len(steps) - index))
        if slice_s < MIN_STAGE_S:
            for skipped in steps[index:]:
                stages.append(f"relax:{skipped.name} SKIPPED")
                outcomes.append(f"{skipped.name}=SKIPPED")
            break
        result, status = _run_relax_step(data, step, slice_s=slice_s, config=config)
        stages.append(f"relax:{step.name} {status}")
        outcomes.append(f"{step.name}={status}")
        if result is not None:
            return result, step, outcomes
    return None, None, outcomes


def _relax_violations(data: TimetableData, result: Phase1Result, step: _RelaxStep) -> dict[str, int]:
    """Count the D7 (and, when dropped, D6) violations left by a relaxed phase-1 map."""
    counts = {"d7_violations": len(sibling_violations(data, result.activity_day))}
    if step.drops_d6:
        counts["d6_violations"] = len(pool_violations(data, result.activity_day, result.activity_start))
    return counts


def _portfolio_phase2(
    data: TimetableData, candidates: list[Phase1Result], *, deadline: Deadline, stages: list[str]
) -> _Solved:
    """Phase 2 per candidate: accept the first clean one, else the first complete diagnostic, else the
    partial result with the fewest sessions left without room."""
    inherited_rooms, inherited_cohorts = _issue_keys(data, None)
    diagnostic: _Solved | None = None
    partial: _Solved | None = None
    outcome: _Solved | None = None
    for index, candidate in enumerate(candidates):
        if index > 0 and deadline.remaining() < PORTFOLIO_RETRY_MIN_S:
            stages.append(f"phase2: no time left for candidate {index}")
            break
        timed = expand_phase1_to_assignments(data, candidate)
        phase2 = solve_phase2(data, timed, max_time_s=max(MIN_STAGE_S, deadline.remaining()), r8_soft_fallback=True)
        stages.append(f"phase2[{index}]: phase1={candidate.status} status={phase2.status} ok={phase2.ok}")
        if not phase2.ok:
            outcome = _Solved(candidate, phase2, failure=f"phase2 failed: {phase2.status} {phase2.message}")
            continue
        rooms_keys, cohort_keys = _issue_keys(data, phase2.assignments)
        rooms = len(rooms_keys - inherited_rooms)
        cohorts = len(cohort_keys - inherited_cohorts)
        stages.append(f"audit: new_room_overlaps={rooms} new_cohort_clashes={cohorts}")
        solved = _Solved(candidate, phase2, new_room_overlaps=rooms, new_cohort_clashes=cohorts)
        if phase2.unassigned:
            stages.append(f"phase2[{index}]: partial unassigned_rooms={len(phase2.unassigned)}")
            if partial is None or partial.phase2 is None or len(phase2.unassigned) < len(partial.phase2.unassigned):
                partial = solved
            continue
        if rooms == 0 and cohorts == 0:
            return solved
        diagnostic = diagnostic or solved
    result = diagnostic or partial or outcome
    if result is None:
        raise ValueError("phase 2 needs at least one candidate")
    return result


def _solve_portfolio(data: TimetableData, *, budget: int, config: PortfolioConfig) -> _Solved:
    split = split_portfolio(float(budget))
    deadline = Deadline(float(budget))
    rules = Phase1Rules()
    res = run_portfolio(data, config=config, budget=split, rules=rules)
    stages = [f"portfolio: {stage}" for stage in res.stages]
    failure = f"phase1 failed: {res.best.status} {res.best.message}"
    steps = RELAX_LADDER
    if res.best.status == "INFEASIBLE_DATA":
        steps = _precheck_relax_steps(res.blocking_codes)
        if not steps:
            return _Solved(res.best, None, tuple(stages), failure=failure)
        stages.append(f"relax: from precheck {', '.join(res.blocking_codes)}")
    relax_counts: dict[str, int] = {}
    if res.best.ok:
        candidates = list(res.ranked)
    else:
        reserve_s = max(MIN_STAGE_S, split.phase2_s)
        relaxed, step, outcomes = _relax_ladder(
            data, deadline=deadline, reserve_s=reserve_s, config=config, stages=stages, steps=steps
        )
        if relaxed is None or step is None:
            return _Solved(res.best, None, tuple(stages), failure=f"{failure}; relax: {', '.join(outcomes)}")
        relax_counts = _relax_violations(data, relaxed, step)
        stages.extend(f"relax: {key}={value}" for key, value in relax_counts.items())
        candidates = [relaxed]
    solved = _portfolio_phase2(data, candidates, deadline=deadline, stages=stages)
    extra: dict[str, Any] = {
        "seed": config.seed,
        "size": config.size,
        "top_k": config.top_k,
        "n_effective": res.n_effective,
        "winner_status": solved.phase1.status,
        "phase1_score": asdict(score_phase1(data, solved.phase1)),
        "stage_reports": list(stages),
        "new_room_overlaps": solved.new_room_overlaps,
        "new_cohort_clashes": solved.new_cohort_clashes,
        **relax_counts,
    }
    return replace(solved, stage_reports=tuple(stages), extra_metrics=extra)


def _deficit_dicts(rows: tuple[DeficitRow, ...]) -> list[dict[str, Any]]:
    return [
        {
            "code": row.code,
            "kind": row.kind,
            "max_simultaneous": row.max_simultaneous,
            "real_teachers": row.real_teachers,
            "deficit": row.deficit,
        }
        for row in rows
    ]


def _summary(strategy: str, solved: _Solved, phase2: Phase2Result, out_csv: Path) -> str:
    body = (
        f"sessions={len(phase2.assignments)} strategy={strategy} "
        f"phase1={solved.phase1.status} obj1={solved.phase1.objective} "
        f"phase2={phase2.status} obj2={phase2.objective} "
        f"r8_relaxed={phase2.r8_relaxed} out={out_csv}"
    )
    prefixes: list[str] = []
    if phase2.unassigned:
        prefixes.append(f"partial: unassigned_rooms={len(phase2.unassigned)}")
    if solved.new_room_overlaps or solved.new_cohort_clashes:
        prefixes.append(
            f"diagnostic export: new_room_overlaps={solved.new_room_overlaps} "
            f"new_cohort_clashes={solved.new_cohort_clashes}"
        )
    return f"{' '.join(prefixes) or 'ok'} {body}"


def solve_and_export(
    *,
    out_csv: Path,
    paquet: Path | None = None,
    db: Path | None = None,
    semestre: int | None = None,
    cursos: str | frozenset[str] | None = None,
    titulacions: str | frozenset[str] | None = None,
    max_time_s: int | None = None,
    json_out: Path | None = None,
    strategy: str = "hybrid",
    portfolio: PortfolioConfig | None = None,
    deficit_out: Path | None = None,
) -> SolveExportResult:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(STRATEGIES)}")
    budget = max_time_s if max_time_s is not None else default_max_time_s()
    if strategy == "portfolio" and budget < PORTFOLIO_MIN_TOTAL_S:
        return SolveExportResult(False, f"portfolio needs --max-time >= {PORTFOLIO_MIN_TOTAL_S:g}", out_csv)

    cursos_set = cursos if isinstance(cursos, frozenset) else parse_cursos(cursos)
    tits_set = titulacions if isinstance(titulacions, frozenset) else parse_titulacions(titulacions)
    data = _load_data(
        paquet=paquet,
        db=db,
        semestre=semestre,
        cursos=cursos_set,
        titulacions=tits_set,
    )
    if not data.sessions:
        return SolveExportResult(False, "no sessions after filter", out_csv)

    if strategy == "portfolio":
        solved = _solve_portfolio(data, budget=budget, config=portfolio or PortfolioConfig())
    else:
        solved = _solve_classic(data, strategy=strategy, budget=budget)
    phase2 = solved.phase2
    if solved.failure is not None or phase2 is None:
        return SolveExportResult(False, solved.failure or "phase2 failed", out_csv, stage_reports=solved.stage_reports)
    clean = solved.new_room_overlaps == 0 and solved.new_cohort_clashes == 0
    complete = not phase2.unassigned
    json_status = "ok" if clean and complete else ("diagnostic" if complete else "partial")

    online_ids = frozenset(s.id for s in data.sessions.values() if s.online)
    write_proposta_csv(out_csv, phase2.assignments, order=data.order, online_ids=online_ids)
    deficit_rows: tuple[DeficitRow, ...] | None = None
    if deficit_out is not None:
        deficit_rows = compute_deficit(data, phase2.assignments)
        write_deficit_csv(deficit_out, deficit_rows)
    if json_out is not None:
        metrics: dict[str, Any] = {
            "strategy": strategy,
            "phase1": solved.phase1.status,
            "phase2": phase2.status,
            "phase1_objective": solved.phase1.objective,
            "phase2_objective": phase2.objective,
            "r8_relaxed": phase2.r8_relaxed,
            "sessions": len(phase2.assignments),
            "unassigned_rooms": len(phase2.unassigned),
            **(solved.extra_metrics or {}),
        }
        if deficit_rows is not None:
            metrics["deficit"] = _deficit_dicts(deficit_rows)
        write_rich_json(json_out, data, phase2.assignments, status=json_status, metrics=metrics)

    return SolveExportResult(
        clean and complete,
        _summary(strategy, solved, phase2, out_csv),
        out_csv,
        r8_relaxed=phase2.r8_relaxed,
        stage_reports=solved.stage_reports,
    )
