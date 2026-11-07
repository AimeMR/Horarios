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
    solve.add_argument(
        "--curs",
        type=str,
        default=None,
        help="Comma-separated grades to include: 1r,2n,3r,4t (optional M,?)",
    )
    solve.add_argument(
        "--titulacio",
        type=str,
        default=None,
        help="Comma-separated degrees: GEI,GEET,GEST,GED,...",
    )
    solve.add_argument("--max-time", type=int, default=None, help="Solver wall time in seconds")
    solve.add_argument(
        "--strategy",
        choices=("hybrid", "greedy", "cpsat"),
        default="hybrid",
        help="hybrid=greedy then CP-SAT hints; keep greedy if CP-SAT UNKNOWN",
    )
    solve.add_argument("--json-out", type=Path, default=None, help="Optional rich JSON for React")

    audit = sub.add_parser(
        "audit-overlaps",
        help="List room double-bookings (R4-AULA) for partida or a proposal CSV",
    )
    audit_src = audit.add_mutually_exclusive_group(required=False)
    audit_src.add_argument("--db", type=Path, help="SQLite DB path. Default: HORARIS_DB")
    audit_src.add_argument("--paquet", type=Path, help="CSV paquet. Default: HORARIS_PAQUET")
    audit.add_argument("--semestre", type=int, choices=(1, 2), default=None)
    audit.add_argument(
        "--curs",
        type=str,
        default=None,
        help="Comma-separated grades filter: 1r,2n,3r,4t",
    )
    audit.add_argument(
        "--titulacio",
        type=str,
        default=None,
        help="Comma-separated degrees filter: GEI,GEET,...",
    )
    audit.add_argument(
        "--proposta",
        type=Path,
        default=None,
        help="Proposal CSV to audit. If omitted, audits aula_partida (official schedule).",
    )
    audit.add_argument("--limit", type=int, default=30, help="Max overlap lines to print")

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
            cursos=args.curs,
            titulacions=args.titulacio,
            max_time_s=args.max_time,
            json_out=args.json_out,
            strategy=args.strategy,
        )
        print(result.summary)
        return 0 if result.ok else 1

    if args.command == "audit-overlaps":
        from horaris_solver.audit.cohort_clashes import find_cohort_clashes
        from horaris_solver.audit.overlaps import find_room_overlaps
        from horaris_solver.domain.filters import parse_cursos, parse_titulacions
        from horaris_solver.export.csv_proposta import read_proposta_csv
        from horaris_solver.solver.pipeline import _load_data

        cursos = parse_cursos(args.curs)
        tits = parse_titulacions(args.titulacio)
        data = _load_data(
            paquet=args.paquet,
            db=args.db,
            semestre=args.semestre,
            cursos=cursos,
            titulacions=tits,
        )
        if args.proposta is not None:
            if not args.proposta.is_file():
                print(
                    f"proposta not found: {args.proposta} "
                    "(solve probably failed before writing the CSV)"
                )
                return 2
            assignments = read_proposta_csv(args.proposta)
            room_hits = find_room_overlaps(data, assignments)
            cohort_hits = find_cohort_clashes(data, assignments)
            source = f"proposta {args.proposta}"
        else:
            room_hits = find_room_overlaps(data, use_partida=True)
            cohort_hits = find_cohort_clashes(data, use_partida=True)
            source = "partida (aula_partida)"

        print(
            f"sessions={len(data.sessions)} source={source} "
            f"room_overlaps={len(room_hits)} cohort_clashes={len(cohort_hits)} "
            f"semestre={args.semestre} curs={args.curs or '*'}"
        )
        if room_hits:
            print("--- room overlaps ---")
            for room_item in room_hits[: max(0, args.limit)]:
                print(room_item.summary())
            if len(room_hits) > args.limit > 0:
                print(f"... and {len(room_hits) - args.limit} more rooms")
        if cohort_hits:
            print("--- cohort clashes ---")
            for cohort_item in cohort_hits[: max(0, args.limit)]:
                print(cohort_item.summary())
            if len(cohort_hits) > args.limit > 0:
                print(f"... and {len(cohort_hits) - args.limit} more cohorts")
        return 1 if room_hits or cohort_hits else 0

    parser.error(f"unknown command: {args.command}")
    return 2
