"""Benchmark solver strategies over several seeds and compare them with the official verifier.

Writes only inside ``<repo>/out/``: ``results.csv`` (one row per strategy x seed) and ``summary.md``
(medians and the acceptance table of plan §8). Outputs carry counts only, never names or ids.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.check_bridge import run_official_check
from horaris_solver.domain.filters import parse_cursos
from horaris_solver.export.csv_proposta import read_proposta_csv
from horaris_solver.solver.pipeline import solve_and_export
from horaris_solver.solver.portfolio import MAX_SEED, PortfolioConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "out"
VERIFIER_TIMEOUT_S = 900.0
ALLOWED_STRATEGIES = ("hybrid", "greedy", "cpsat", "portfolio")
BASELINE = "hybrid"
RULES = (
    "R0-FORMAT",
    "R0-HORARI",
    "R1-FIXADA",
    "R1-TORN",
    "R2-FINESTRA",
    "R2-CALENDARI",
    "R3-AULA",
    "R3-AFORAMENT",
    "R3-TIPUS",
    "R3-TANCADA",
    "R4-AULA",
    "R4-DOCENT",
    "R4-ALUMNAT",
    "R4-PLAB",
    "R4-COMPARTIDA",
    "R5-FALTA",
    "R5-SENSE-AULA",
    "R5-RECUPERACIO",
    "R7-PLAB",
    "R8-RESERVA",
)
OBJECTIVES = ("hores_mortes_min", "canvis_franja", "canvis_aula", "r6_canvis_te_paul_fora_passadis")
CRITERIA = ("feasibility", "hard_counted", "fixed_rules", "hores_mortes", "canvis_franja", "wall")
IMPROVEMENT = 0.9
WALL_SLACK = 1.05

_RULE_LINE = re.compile(r"^\s*\[(?:OK |KO )\]\s+(R\d[A-Z0-9-]*)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s|$)")
_OBJECTIVE_LINE = re.compile(r"^\s*(" + "|".join(OBJECTIVES) + r")\s+(-?\d+)\s*$")
_VERDICT_LINE = re.compile(r"^\s*Veredicte:\s*(NO VALIDA|VALIDA)\b")
_STATUS_PREFIX = re.compile(r"^(ok|no sessions after filter|phase\d failed: [A-Z_]+)")


@dataclass(frozen=True)
class VerifierReport:
    rules: dict[str, tuple[int, int, int]]
    objectives: dict[str, int]
    valid: bool | None


@dataclass(frozen=True)
class RunResult:
    strategy: str
    seed: int
    ok: bool
    status_summary: str
    wall_s: float
    sessions: int | None
    counted: dict[str, int] = field(default_factory=dict)
    r5_extra: int | None = None
    objectives: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Acceptance:
    strategy: str
    criterion: str
    status: str
    detail: str


def resolve_out_dir(raw: str) -> Path:
    """Resolve ``raw`` against the repo root and accept it only inside ``<repo>/out/``; create it."""
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(OUT_ROOT.resolve()):
        raise ValueError("--out-dir must be inside the repository out/ directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def parse_verifier_output(output: str) -> VerifierReport:
    """Read only the leading tokens of each line; description text may be garbled."""
    rules: dict[str, tuple[int, int, int]] = {}
    objectives: dict[str, int] = {}
    valid: bool | None = None
    for line in output.splitlines():
        if match := _RULE_LINE.match(line):
            rules[match.group(1)] = (int(match.group(2)), int(match.group(3)), int(match.group(4)))
        elif match := _OBJECTIVE_LINE.match(line):
            objectives[match.group(1)] = int(match.group(2))
        elif match := _VERDICT_LINE.match(line):
            valid = match.group(1) == "VALIDA"
    return VerifierReport(rules=rules, objectives=objectives, valid=valid)


def r5_extra(*, r5_falta: int | None, total_sessions: int, filtered_sessions: int) -> int | None:
    """R5-FALTA beyond the sessions a filtered run is expected to miss (the verifier checks the whole semester)."""
    if r5_falta is None:
        return None
    return r5_falta - (total_sessions - filtered_sessions)


def count_sessions(paquet: Path, semestre: int, cursos: frozenset[str] | None) -> int:
    return len(CsvTimetableSource(paquet).load(semestre=semestre, cursos=cursos).sessions)


def count_placed(proposal_csv: Path) -> int:
    return len(read_proposta_csv(proposal_csv))


def short_status(summary: str) -> str:
    match = _STATUS_PREFIX.match(summary)
    return match.group(1) if match else "failed"


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def _hard_counted(run: RunResult) -> int | None:
    if not run.counted or run.r5_extra is None:
        return None
    return sum(v for rule, v in run.counted.items() if rule != "R5-FALTA") + run.r5_extra


def _objective_values(runs: Sequence[RunResult], name: str) -> list[float]:
    return [float(r.objectives[name]) for r in runs if r.ok and name in r.objectives]


def _feasibility(runs: Sequence[RunResult], base: Sequence[RunResult]) -> Acceptance:
    base_ok = {r.seed: r.ok for r in base}
    worse = [r.seed for r in runs if not r.ok and base_ok.get(r.seed, False)]
    detail = f"{sum(r.ok for r in runs)}/{len(runs)} feasible vs {sum(r.ok for r in base)}/{len(base)} hybrid"
    return Acceptance("", "feasibility", "FAIL" if worse else "PASS", detail)


def _zero_check(runs: Sequence[RunResult], criterion: str, values: list[int]) -> Acceptance:
    if not values:
        return Acceptance("", criterion, "N/A", "no official data")
    return Acceptance("", criterion, "PASS" if max(values) == 0 else "FAIL", f"max={max(values)}")


def _improvement(runs: Sequence[RunResult], base: Sequence[RunResult], name: str, criterion: str) -> Acceptance:
    mine = _median(_objective_values(runs, name))
    ref = _median(_objective_values(base, name))
    if mine is None or ref is None:
        return Acceptance("", criterion, "N/A", "missing data")
    status = "PASS" if mine <= IMPROVEMENT * ref else "FAIL"
    return Acceptance("", criterion, status, f"median {mine:g} vs hybrid {ref:g} (target <= {IMPROVEMENT * ref:g})")


def _evaluate_strategy(runs: Sequence[RunResult], base: Sequence[RunResult], max_time_s: float) -> list[Acceptance]:
    hard = [h for r in runs if r.ok and (h := _hard_counted(r)) is not None]
    fixed = [r.counted[k] for r in runs if r.ok for k in ("R1-FIXADA", "R7-PLAB") if k in r.counted]
    max_wall = max(r.wall_s for r in runs)
    limit = WALL_SLACK * max_time_s
    return [
        _feasibility(runs, base),
        _zero_check(runs, "hard_counted", hard),
        _zero_check(runs, "fixed_rules", fixed),
        _improvement(runs, base, "hores_mortes_min", "hores_mortes"),
        _improvement(runs, base, "canvis_franja", "canvis_franja"),
        Acceptance("", "wall", "PASS" if max_wall <= limit else "FAIL", f"max {max_wall:.1f}s (limit {limit:g}s)"),
    ]


def evaluate_acceptance(runs: Sequence[RunResult], *, max_time_s: float) -> list[Acceptance]:
    """Plan §8 acceptance per non-baseline strategy, compared seed by seed with ``hybrid``."""
    base = [r for r in runs if r.strategy == BASELINE]
    strategies = list(dict.fromkeys(r.strategy for r in runs if r.strategy != BASELINE))
    out: list[Acceptance] = []
    for strategy in strategies:
        mine = [r for r in runs if r.strategy == strategy]
        for item in _evaluate_strategy(mine, base, max_time_s):
            out.append(Acceptance(strategy, item.criterion, item.status, item.detail))
    return out


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


def write_results_csv(path: Path, runs: Sequence[RunResult]) -> None:
    header = ["strategy", "seed", "ok", "status_summary", "wall_s", "sessions", *RULES, "r5_extra", *OBJECTIVES]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r in runs:
            writer.writerow(
                [
                    r.strategy,
                    r.seed,
                    r.ok,
                    r.status_summary,
                    f"{r.wall_s:.2f}",
                    _fmt(r.sessions),
                    *(_fmt(r.counted.get(rule)) for rule in RULES),
                    _fmt(r.r5_extra),
                    *(_fmt(r.objectives.get(name)) for name in OBJECTIVES),
                ]
            )


def _median_row(strategy: str, runs: Sequence[RunResult]) -> str:
    hard = [float(h) for r in runs if r.ok and (h := _hard_counted(r)) is not None]
    cells = [
        strategy,
        str(len(runs)),
        str(sum(r.ok for r in runs)),
        _fmt(_median([r.wall_s for r in runs])),
        _fmt(_median(hard)),
        *(_fmt(_median(_objective_values(runs, name))) for name in OBJECTIVES),
    ]
    return "| " + " | ".join(cells) + " |"


def write_summary_md(path: Path, runs: Sequence[RunResult], *, max_time_s: float) -> None:
    strategies = list(dict.fromkeys(r.strategy for r in runs))
    lines = [
        "# Benchmark summary",
        "",
        f"Budget T = {max_time_s:g} s. Hard counted = counted verifier violations without R5-FALTA, plus r5_extra.",
        "",
        "## Medians per strategy",
        "",
        "| strategy | runs | feasible | wall_s | hard_counted | " + " | ".join(OBJECTIVES) + " |",
        "|" + "---|" * (5 + len(OBJECTIVES)),
    ]
    lines += [_median_row(s, [r for r in runs if r.strategy == s]) for s in strategies]
    lines += [
        "",
        "## Acceptance (plan §8, vs hybrid)",
        "",
        "| strategy | criterion | status | detail |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {a.strategy} | {a.criterion} | {a.status} | {a.detail} |"
        for a in evaluate_acceptance(runs, max_time_s=max_time_s)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class BenchConfig:
    paquet: Path
    semestre: int
    curs: str | None
    strategies: tuple[str, ...]
    seeds: tuple[int, ...]
    max_time_s: int
    out_dir: Path
    official: bool


def _run_one(cfg: BenchConfig, strategy: str, seed: int, counts: tuple[int, int]) -> RunResult:
    out_csv = cfg.out_dir / f"{strategy}_s{seed}.csv"
    portfolio = PortfolioConfig(seed=seed) if strategy == "portfolio" else None
    start = time.monotonic()
    result = solve_and_export(
        out_csv=out_csv,
        paquet=cfg.paquet,
        semestre=cfg.semestre,
        cursos=cfg.curs,
        max_time_s=cfg.max_time_s,
        strategy=strategy,
        portfolio=portfolio,
    )
    wall = time.monotonic() - start
    has_csv = result.ok and out_csv.is_file()
    sessions = count_placed(out_csv) if has_csv else None
    if not (has_csv and cfg.official):
        return RunResult(strategy, seed, result.ok, short_status(result.summary), wall, sessions)
    _rc, output = run_official_check(out_csv, semestre=cfg.semestre, paquet=cfg.paquet, timeout_s=VERIFIER_TIMEOUT_S)
    report = parse_verifier_output(output)
    counted = {rule: values[0] for rule, values in report.rules.items()}
    extra = r5_extra(r5_falta=counted.get("R5-FALTA"), total_sessions=counts[0], filtered_sessions=counts[1])
    return RunResult(
        strategy, seed, result.ok, short_status(result.summary), wall, sessions, counted, extra, report.objectives
    )


def run_benchmark(cfg: BenchConfig) -> list[RunResult]:
    counts = (0, 0)
    if cfg.official and cfg.curs:
        total = count_sessions(cfg.paquet, cfg.semestre, None)
        counts = (total, count_sessions(cfg.paquet, cfg.semestre, parse_cursos(cfg.curs)))
    runs = [_run_one(cfg, s, seed, counts) for s in cfg.strategies for seed in cfg.seeds]
    write_results_csv(cfg.out_dir / "results.csv", runs)
    write_summary_md(cfg.out_dir / "summary.md", runs, max_time_s=cfg.max_time_s)
    return runs


def _parse_strategies(raw: str) -> tuple[str, ...]:
    items = tuple(dict.fromkeys(p.strip() for p in raw.split(",") if p.strip()))
    if not items or any(s not in ALLOWED_STRATEGIES for s in items):
        raise ValueError(f"--strategies must be a comma list of {', '.join(ALLOWED_STRATEGIES)}")
    return items


def _parse_seeds(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError("--seeds must be a comma list of non-negative integers")
    seeds = tuple(dict.fromkeys(int(p) for p in parts))
    if any(s > MAX_SEED for s in seeds):
        raise ValueError(f"--seeds must be <= {MAX_SEED}")
    return seeds


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m horaris_solver.benchmark", description=__doc__)
    parser.add_argument("--paquet", type=Path, required=True)
    parser.add_argument("--semestre", type=int, required=True, choices=(1, 2))
    parser.add_argument("--curs", default=None)
    parser.add_argument("--strategies", default="hybrid,portfolio")
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--max-time", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--no-official", action="store_true")
    return parser


def _config(args: argparse.Namespace) -> BenchConfig:
    if args.max_time < 1:
        raise ValueError("--max-time must be >= 1")
    strategies = _parse_strategies(args.strategies)
    seeds = _parse_seeds(args.seeds)
    parse_cursos(args.curs)
    return BenchConfig(
        paquet=args.paquet,
        semestre=args.semestre,
        curs=args.curs,
        strategies=strategies,
        seeds=seeds,
        max_time_s=args.max_time,
        out_dir=resolve_out_dir(args.out_dir),
        official=not args.no_official,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        cfg = _config(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        runs = run_benchmark(cfg)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{len(runs)} runs written to {cfg.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
