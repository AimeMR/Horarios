"""Orchestrate load → phase1 → phase2 → export."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.adapters.sqlite_loader import SqliteTimetableSource
from horaris_solver.domain.models import TimetableData
from horaris_solver.export.csv_proposta import write_proposta_csv
from horaris_solver.export.json_rich import write_rich_json
from horaris_solver.solver.phase1_time import expand_phase1_to_assignments, solve_phase1
from horaris_solver.solver.phase2_rooms import solve_phase2


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
) -> TimetableData:
    if db is not None and paquet is not None:
        raise ValueError("pass either --db or --paquet, not both")
    if db is not None:
        return SqliteTimetableSource(db).load(semestre=semestre)
    if paquet is not None:
        return CsvTimetableSource(paquet).load(semestre=semestre)
    env_db = os.environ.get("HORARIS_DB", "").strip()
    if env_db:
        return SqliteTimetableSource(Path(env_db)).load(semestre=semestre)
    env_paquet = os.environ.get("HORARIS_PAQUET", "").strip()
    if env_paquet:
        return CsvTimetableSource(Path(env_paquet)).load(semestre=semestre)
    raise ValueError("provide --db, --paquet, or set HORARIS_DB / HORARIS_PAQUET")


def solve_and_export(
    *,
    out_csv: Path,
    paquet: Path | None = None,
    db: Path | None = None,
    semestre: int | None = None,
    max_time_s: int | None = None,
    json_out: Path | None = None,
) -> SolveExportResult:
    budget = max_time_s if max_time_s is not None else default_max_time_s()
    phase1_budget = max(30, budget // 2)
    phase2_budget = max(30, budget - phase1_budget)

    data = _load_data(paquet=paquet, db=db, semestre=semestre)
    if not data.sessions:
        return SolveExportResult(False, "no sessions after filter", out_csv)

    phase1 = solve_phase1(data, max_time_s=phase1_budget)
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
                "phase1": phase1.status,
                "phase2": phase2.status,
                "phase1_objective": phase1.objective,
                "phase2_objective": phase2.objective,
                "r8_relaxed": phase2.r8_relaxed,
                "sessions": len(phase2.assignments),
            },
        )

    summary = (
        f"ok sessions={len(phase2.assignments)} "
        f"phase1={phase1.status} obj1={phase1.objective} "
        f"phase2={phase2.status} obj2={phase2.objective} "
        f"r8_relaxed={phase2.r8_relaxed} out={out_csv}"
    )
    return SolveExportResult(True, summary, out_csv, r8_relaxed=phase2.r8_relaxed)
