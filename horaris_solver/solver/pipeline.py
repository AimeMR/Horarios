"""Orchestrate load → phase1 (CP-SAT / greedy) → phase2 → export."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.adapters.sqlite_loader import SqliteTimetableSource
from horaris_solver.domain.filters import parse_cursos, parse_titulacions
from horaris_solver.domain.models import TimetableData
from horaris_solver.export.csv_proposta import write_proposta_csv
from horaris_solver.export.json_rich import write_rich_json
from horaris_solver.solver.greedy_phase1 import solve_phase1_greedy
from horaris_solver.solver.phase1_time import (
    Phase1Result,
    expand_phase1_to_assignments,
    solve_phase1,
)
from horaris_solver.solver.phase2_rooms import solve_phase2

STRATEGIES = frozenset({"hybrid", "greedy", "cpsat"})


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
        return SqliteTimetableSource(db).load(
            semestre=semestre, cursos=cursos, titulacions=titulacions
        )
    if paquet is not None:
        return CsvTimetableSource(paquet).load(
            semestre=semestre, cursos=cursos, titulacions=titulacions
        )
    env_db = os.environ.get("HORARIS_DB", "").strip()
    if env_db:
        return SqliteTimetableSource(Path(env_db)).load(
            semestre=semestre, cursos=cursos, titulacions=titulacions
        )
    env_paquet = os.environ.get("HORARIS_PAQUET", "").strip()
    if env_paquet:
        return CsvTimetableSource(Path(env_paquet)).load(
            semestre=semestre, cursos=cursos, titulacions=titulacions
        )
    raise ValueError("provide --db, --paquet, or set HORARIS_DB / HORARIS_PAQUET")


def _run_phase1(
    data: TimetableData,
    *,
    strategy: str,
    max_time_s: int,
) -> Phase1Result:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(STRATEGIES)}")
    if strategy == "greedy":
        return solve_phase1_greedy(data)
    if strategy == "cpsat":
        return solve_phase1(data, max_time_s=max_time_s)
    # hybrid: greedy warm pack, then CP-SAT; if CP-SAT fails keep greedy when feasible
    greedy = solve_phase1_greedy(data)
    cpsat = solve_phase1(
        data,
        max_time_s=max_time_s,
        hints=greedy,
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
) -> SolveExportResult:
    budget = max_time_s if max_time_s is not None else default_max_time_s()
    phase1_budget = max(30, budget // 2)
    phase2_budget = max(30, budget - phase1_budget)

    cursos_set = cursos if isinstance(cursos, frozenset) else parse_cursos(cursos)
    tits_set = (
        titulacions
        if isinstance(titulacions, frozenset)
        else parse_titulacions(titulacions)
    )
    data = _load_data(
        paquet=paquet,
        db=db,
        semestre=semestre,
        cursos=cursos_set,
        titulacions=tits_set,
    )
    if not data.sessions:
        return SolveExportResult(False, "no sessions after filter", out_csv)

    phase1 = _run_phase1(data, strategy=strategy, max_time_s=phase1_budget)
    if not phase1.ok:
        return SolveExportResult(False, f"phase1 failed: {phase1.status} {phase1.message}", out_csv)

    timed = expand_phase1_to_assignments(data, phase1)
    phase2 = solve_phase2(data, timed, max_time_s=phase2_budget, r8_soft_fallback=True)
    if not phase2.ok:
        return SolveExportResult(False, f"phase2 failed: {phase2.status} {phase2.message}", out_csv)

    write_proposta_csv(out_csv, phase2.assignments, order=data.order)
    if json_out is not None:
        write_rich_json(
            json_out,
            data,
            phase2.assignments,
            status="ok",
            metrics={
                "strategy": strategy,
                "phase1": phase1.status,
                "phase2": phase2.status,
                "phase1_objective": phase1.objective,
                "phase2_objective": phase2.objective,
                "r8_relaxed": phase2.r8_relaxed,
                "sessions": len(phase2.assignments),
            },
        )

    summary = (
        f"ok sessions={len(phase2.assignments)} strategy={strategy} "
        f"phase1={phase1.status} obj1={phase1.objective} "
        f"phase2={phase2.status} obj2={phase2.objective} "
        f"r8_relaxed={phase2.r8_relaxed} out={out_csv}"
    )
    return SolveExportResult(True, summary, out_csv, r8_relaxed=phase2.r8_relaxed)
