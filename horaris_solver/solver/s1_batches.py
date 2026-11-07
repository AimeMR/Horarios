"""Semestre-1 morning/afternoon batch driver (primaries + optional ladder)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from horaris_solver.domain.models import TimetableData
from horaris_solver.solver.pipeline import STRATEGIES, SolveExportResult, solve_and_export

SEMESTRE_S1 = 1
MORNING_CURS = "1r,2n"
AFTERNOON_CURS = "3r,4t,M,?"
GEET_GEST = frozenset({"GEET", "GEST"})
DEFAULT_2N_TITS = frozenset({"GEI", "GED", "GEET", "GEST"})


class SolveFn(Protocol):
    def __call__(
        self,
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
    ) -> SolveExportResult: ...


@dataclass(frozen=True)
class BatchSpec:
    batch_id: str
    cursos: str
    titulacions: str | None
    out_name: str
    role: str


@dataclass(frozen=True)
class BatchOutcome:
    spec: BatchSpec
    ok: bool
    phase1_status: str
    phase2_status: str
    summary: str
    csv_path: Path | None
    sessions: int


@dataclass(frozen=True)
class BatchRunReport:
    outcomes: tuple[BatchOutcome, ...]
    conclusions_path: Path
    morning_ok: bool
    afternoon_ok: bool
    used_ladder: bool


def titulacions_from_data(data: TimetableData) -> frozenset[str]:
    found: set[str] = set()
    for session in data.sessions.values():
        for cohort in session.cohorts:
            if ":" not in cohort:
                continue
            found.add(cohort.split(":", 1)[0].upper())
    return frozenset(found)


def format_titulacions(tits: frozenset[str]) -> str:
    return ",".join(sorted(tits))


def morning_primary_spec() -> BatchSpec:
    return BatchSpec("s1_morning", MORNING_CURS, None, "proposta_s1_1r2n.csv", "primary")


def afternoon_primary_spec() -> BatchSpec:
    return BatchSpec("s1_afternoon", AFTERNOON_CURS, None, "proposta_s1_3r4t.csv", "primary")


def morning_ladder_specs(available_2n_tits: frozenset[str]) -> tuple[BatchSpec, ...]:
    specs: list[BatchSpec] = [
        BatchSpec("s1_1r", "1r", None, "proposta_s1_1r.csv", "ladder"),
    ]
    available = frozenset(tit.upper() for tit in available_2n_tits)
    core = available - GEET_GEST
    if core:
        specs.append(
            BatchSpec(
                "s1_2n_core",
                "2n",
                format_titulacions(core),
                "proposta_s1_2n_core.csv",
                "ladder",
            )
        )
    if available & GEET_GEST:
        specs.append(
            BatchSpec(
                "s1_2n_geet_gest",
                "2n",
                format_titulacions(GEET_GEST),
                "proposta_s1_2n_geet_gest.csv",
                "diagnostic",
            )
        )
    return tuple(specs)


def write_conclusions(report: BatchRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# S1 batch conclusions",
        "",
        f"- written_at: {datetime.now(tz=UTC).isoformat()}",
        f"- morning_ok: {report.morning_ok}",
        f"- afternoon_ok: {report.afternoon_ok}",
        f"- used_ladder: {report.used_ladder}",
        "",
        "| batch_id | curs | titulacio | role | ok | summary |",
        "|---|---|---|---|---|---|",
    ]
    for outcome in report.outcomes:
        tits = outcome.spec.titulacions or ""
        lines.append(
            f"| {outcome.spec.batch_id} | {outcome.spec.cursos} | {tits} | "
            f"{outcome.spec.role} | {outcome.ok} | {outcome.summary} |"
        )
    lines.extend(["", "## Notes", ""])
    if not report.morning_ok:
        lines.append(
            "- Morning primary failed. Ladder CSVs are diagnostic and not jury-mergeable."
        )
    geet_failed = any(
        (not outcome.ok)
        and outcome.spec.titulacions is not None
        and "GEET" in outcome.spec.titulacions
        and "GEST" in outcome.spec.titulacions
        for outcome in report.outcomes
    )
    if geet_failed:
        lines.append(
            "- GEET/GEST 2n diagnostic failed (INFEASIBLE or UNKNOWN). Recorded; run continued."
        )
    lines.append(
        "- 1r+2n vs 3r+4t share rooms but disjoint turns; do not concat morning ladder CSVs."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _run_spec(
    spec: BatchSpec,
    *,
    solve: SolveFn,
    out_dir: Path,
    paquet: Path | None,
    db: Path | None,
    max_time_s: int | None,
    strategy: str,
) -> BatchOutcome:
    out_csv = out_dir / spec.out_name
    result = solve(
        out_csv=out_csv,
        paquet=paquet,
        db=db,
        semestre=SEMESTRE_S1,
        cursos=spec.cursos,
        titulacions=spec.titulacions,
        max_time_s=max_time_s,
        strategy=strategy,
    )
    return BatchOutcome(
        spec=spec,
        ok=result.ok,
        phase1_status="",
        phase2_status="",
        summary=result.summary,
        csv_path=result.out_csv if result.ok else None,
        sessions=0,
    )


def run_s1_batches(
    *,
    out_dir: Path,
    conclusions_path: Path,
    paquet: Path | None = None,
    db: Path | None = None,
    max_time_s: int | None = None,
    strategy: str = "hybrid",
    solve: SolveFn | None = None,
    allowed_root: Path | None = None,
) -> BatchRunReport:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(STRATEGIES)}")
    if db is None and paquet is None:
        raise ValueError("provide db or paquet")
    if db is not None and not Path(db).is_file():
        raise ValueError(f"db not found: {db}")
    if paquet is not None and not Path(paquet).is_dir():
        raise ValueError(f"paquet not found: {paquet}")

    out_dir = Path(out_dir)
    conclusions_path = Path(conclusions_path)
    if allowed_root is not None:
        root = Path(allowed_root)
        if not _is_inside(out_dir, root) or not _is_inside(conclusions_path, root):
            raise ValueError("out_dir or conclusions path escapes allowed_root")

    out_dir.mkdir(parents=True, exist_ok=True)
    solver: SolveFn = solve if solve is not None else solve_and_export

    available = DEFAULT_2N_TITS
    morning = morning_primary_spec()
    afternoon = afternoon_primary_spec()
    outcomes: list[BatchOutcome] = [
        _run_spec(
            morning,
            solve=solver,
            out_dir=out_dir,
            paquet=paquet,
            db=db,
            max_time_s=max_time_s,
            strategy=strategy,
        )
    ]
    used_ladder = False
    if not outcomes[0].ok:
        used_ladder = True
        for spec in morning_ladder_specs(available):
            outcomes.append(
                _run_spec(
                    spec,
                    solve=solver,
                    out_dir=out_dir,
                    paquet=paquet,
                    db=db,
                    max_time_s=max_time_s,
                    strategy=strategy,
                )
            )
    afternoon_outcome = _run_spec(
        afternoon,
        solve=solver,
        out_dir=out_dir,
        paquet=paquet,
        db=db,
        max_time_s=max_time_s,
        strategy=strategy,
    )
    outcomes.append(afternoon_outcome)

    report = BatchRunReport(
        outcomes=tuple(outcomes),
        conclusions_path=conclusions_path,
        morning_ok=outcomes[0].ok,
        afternoon_ok=afternoon_outcome.ok,
        used_ladder=used_ladder,
    )
    write_conclusions(report, conclusions_path)
    return report
