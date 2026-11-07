"""CLI entrypoint for the timetable solver."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horaris-solver",
        description="Two-phase CP-SAT timetable solver (Escola d'Enginyeria).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    solve = sub.add_parser("solve", help="Load SQLite DB or CSV paquet, solve, write proposal CSV")
    src = solve.add_mutually_exclusive_group(required=False)
    src.add_argument("--db", type=Path, help="SQLite DB path (team schema). Default: HORARIS_DB")
    src.add_argument("--paquet", type=Path, help="CSV paquet directory. Default: HORARIS_PAQUET")
    solve.add_argument("--out", type=Path, required=True, help="Output proposal CSV path")
    solve.add_argument("--semestre", type=int, choices=(1, 2), default=None)
    solve.add_argument("--max-time", type=int, default=None, help="Solver wall time in seconds")
    solve.add_argument("--json-out", type=Path, default=None, help="Optional rich JSON for React")

    sub.add_parser("version", help="Print package version")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        from horaris_solver import __version__

        print(__version__)
        return 0

    if args.command == "solve":
        from horaris_solver.solver.pipeline import solve_and_export

        result = solve_and_export(
            paquet=args.paquet,
            db=args.db,
            out_csv=args.out,
            semestre=args.semestre,
            max_time_s=args.max_time,
            json_out=args.json_out,
        )
        print(result.summary)
        return 0 if result.ok else 1

    parser.error(f"unknown command: {args.command}")
    return 2
