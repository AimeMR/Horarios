#!/usr/bin/env python3
"""Run Semestre 1 morning (1r+2n) and afternoon (3r+4t,M,?) batches."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from horaris_solver.solver.s1_batches import run_s1_batches  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="S1 morning/afternoon batch solves")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--paquet", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--conclusions", type=Path, required=True)
    parser.add_argument("--strategy", default="hybrid")
    parser.add_argument("--max-time", type=int, default=180)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_s1_batches(
        out_dir=args.out_dir,
        conclusions_path=args.conclusions,
        paquet=args.paquet,
        db=args.db,
        max_time_s=args.max_time,
        strategy=args.strategy,
    )
    print(
        f"morning_ok={report.morning_ok} afternoon_ok={report.afternoon_ok} "
        f"used_ladder={report.used_ladder} conclusions={report.conclusions_path}"
    )
    return 0 if report.morning_ok and report.afternoon_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
