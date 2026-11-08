from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from horaris_solver import benchmark
from horaris_solver.benchmark import (
    REPO_ROOT,
    RunResult,
    evaluate_acceptance,
    parse_verifier_output,
    r5_extra,
    resolve_out_dir,
)
from horaris_solver.solver.pipeline import SolveExportResult

SAMPLE = (
    "Semestre 1: 0 files de l'altre semestre ignorades\n"
    "Veredicte: NO VALIDA\n"
    "Sessions a la base: 9287 \ufffd a la proposta: 2538\n"
    "\n"
    "Restriccions dures          compten  declarades  heretades\n"
    "  [OK ] R0-FORMAT             0           0          0  Proposta mal formada (sessi\ufffd desconeguda)\n"
    "  [OK ] R1-FIXADA             0           0          0  Sessi\ufffd de GEI moguda (no es toca)\n"
    "  [OK ] R1-TORN               0           0        349  1r i 2n al mat\ufffd; 3r\n"
    "  [KO ] R3-AFORAMENT         27           0         78  M\ufffds alumnes que la capacitat\n"
    "  [KO ] R5-FALTA           6749           0          0  Sessi\ufffd de la base que no surt\n"
    "  [OK ] R7-PLAB               0           0          0  Laboratori PLAB mogut\n"
    "  [OK ] R8-RESERVA            0           0          0\n"
    "\n"
    "Objectius\n"
    "  hores_mortes_min         14520\n"
    "  canvis_franja            175\n"
    "  canvis_aula              84\n"
    "  r6_aules_te_extra_per_grup 19\n"
    "  r6_canvis_te_paul_fora_passadis 330\n"
)


# --- out dir ---------------------------------------------------------------


def test_out_dir_inside_out_is_created() -> None:
    target = REPO_ROOT / "out" / "bench" / "pytest_benchmark_tmp"
    try:
        resolved = resolve_out_dir("out/bench/pytest_benchmark_tmp")
        assert resolved == target.resolve()
        assert resolved.is_dir()
    finally:
        if target.is_dir():
            target.rmdir()


@pytest.mark.parametrize(
    "raw",
    [
        "docs/bench",
        "out/../docs",
        "out/bench/../../horaris_solver",
        "..",
        "out_evil/bench",
        "C:/Windows/Temp/bench",
        "../outside/bench",
    ],
)
def test_out_dir_outside_out_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        resolve_out_dir(raw)


def test_out_dir_absolute_outside_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_out_dir(str(tmp_path / "bench"))
    assert not (tmp_path / "bench").exists()


def test_cli_rejects_out_dir_outside_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_: Any) -> SolveExportResult:
        raise AssertionError("must not solve")

    monkeypatch.setattr(benchmark, "solve_and_export", boom)
    rc = benchmark.main(
        [
            "--paquet",
            str(tmp_path),
            "--semestre",
            "1",
            "--strategies",
            "hybrid",
            "--seeds",
            "1",
            "--max-time",
            "10",
            "--out-dir",
            str(tmp_path / "x"),
            "--no-official",
        ]
    )
    assert rc == 2
    assert not (tmp_path / "x").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--strategies", "hybrid,evil"],
        ["--seeds", "1,abc"],
        ["--seeds", "-1"],
        ["--max-time", "0"],
    ],
)
def test_cli_rejects_bad_arguments(args: list[str], tmp_path: Path) -> None:
    base = {
        "--strategies": "hybrid",
        "--seeds": "1",
        "--max-time": "10",
    }
    base[args[0]] = args[1]
    argv = ["--paquet", str(tmp_path), "--semestre", "1", "--out-dir", "out/bench/never", "--no-official"]
    for key, value in base.items():
        argv.extend([key, value])
    assert benchmark.main(argv) == 2
    assert not (REPO_ROOT / "out" / "bench" / "never").exists()


# --- parser ----------------------------------------------------------------


def test_parse_verifier_output_reads_rules_and_objectives() -> None:
    parsed = parse_verifier_output(SAMPLE)
    assert parsed.rules["R1-TORN"] == (0, 0, 349)
    assert parsed.rules["R3-AFORAMENT"] == (27, 0, 78)
    assert parsed.rules["R5-FALTA"] == (6749, 0, 0)
    assert parsed.rules["R8-RESERVA"] == (0, 0, 0)
    assert parsed.objectives == {
        "hores_mortes_min": 14520,
        "canvis_franja": 175,
        "canvis_aula": 84,
        "r6_canvis_te_paul_fora_passadis": 330,
    }
    assert parsed.valid is False


def test_parse_verifier_output_tolerates_garbage() -> None:
    noisy = "\x00\xff\u00e9\ufffd [KO ] broken line\n  [OK ] R1-FIXADA  x  0 0\nrandom \ufffd\ufffd\n"
    parsed = parse_verifier_output(noisy)
    assert parsed.rules == {}
    assert parsed.objectives == {}
    assert parsed.valid is None


def test_parse_verifier_output_valid_verdict() -> None:
    assert parse_verifier_output("Veredicte: VALIDA\n").valid is True


# --- r5 --------------------------------------------------------------------


def test_r5_extra_subtracts_sessions_outside_filter() -> None:
    assert r5_extra(r5_falta=6749, total_sessions=9287, filtered_sessions=2538) == 0
    assert r5_extra(r5_falta=6752, total_sessions=9287, filtered_sessions=2538) == 3


def test_r5_extra_without_filter_is_raw() -> None:
    assert r5_extra(r5_falta=4, total_sessions=100, filtered_sessions=100) == 4


def test_r5_extra_none_when_not_measured() -> None:
    assert r5_extra(r5_falta=None, total_sessions=100, filtered_sessions=50) is None


# --- acceptance --------------------------------------------------------------


def _run(
    strategy: str,
    seed: int,
    *,
    ok: bool = True,
    wall: float = 50.0,
    hm: int | None = 1000,
    cf: int | None = 100,
    counted: dict[str, int] | None = None,
    r5x: int | None = 0,
) -> RunResult:
    return RunResult(
        strategy=strategy,
        seed=seed,
        ok=ok,
        status_summary="ok" if ok else "phase1 failed: INFEASIBLE",
        wall_s=wall,
        sessions=10 if ok else None,
        counted=counted if counted is not None else ({"R1-FIXADA": 0, "R7-PLAB": 0, "R5-FALTA": 5} if ok else {}),
        r5_extra=r5x if ok else None,
        objectives={"hores_mortes_min": hm, "canvis_franja": cf} if ok and hm is not None and cf is not None else {},
    )


def _status(rows: list[tuple[str, str, str]], criterion: str) -> str:
    for strategy, crit, status in rows:
        if strategy == "portfolio" and crit == criterion:
            return status
    raise AssertionError(f"missing {criterion}")


def test_acceptance_all_pass() -> None:
    runs = [_run("hybrid", s) for s in (1, 2, 3)] + [_run("portfolio", s, hm=800, cf=80, wall=100) for s in (1, 2, 3)]
    rows = [(r.strategy, r.criterion, r.status) for r in evaluate_acceptance(runs, max_time_s=100)]
    for criterion in benchmark.CRITERIA:
        assert _status(rows, criterion) == "PASS", criterion
    assert all(strategy != "hybrid" for strategy, _, _ in rows)


def test_acceptance_failures() -> None:
    runs = [_run("hybrid", s) for s in (1, 2, 3)] + [
        _run("portfolio", 1, ok=False, wall=10),
        _run("portfolio", 2, hm=950, cf=95, wall=106, counted={"R1-FIXADA": 2, "R7-PLAB": 0, "R5-FALTA": 0}),
        _run("portfolio", 3, hm=950, cf=95, r5x=1),
    ]
    rows = [(r.strategy, r.criterion, r.status) for r in evaluate_acceptance(runs, max_time_s=100)]
    assert _status(rows, "feasibility") == "FAIL"
    assert _status(rows, "hard_counted") == "FAIL"
    assert _status(rows, "fixed_rules") == "FAIL"
    assert _status(rows, "hores_mortes") == "FAIL"
    assert _status(rows, "canvis_franja") == "FAIL"
    assert _status(rows, "wall") == "FAIL"


def test_acceptance_infeasible_hybrid_counts_as_pass_for_feasibility() -> None:
    runs = [_run("hybrid", 1, ok=False), _run("portfolio", 1)]
    rows = [(r.strategy, r.criterion, r.status) for r in evaluate_acceptance(runs, max_time_s=100)]
    assert _status(rows, "feasibility") == "PASS"
    assert _status(rows, "hores_mortes") == "N/A"


def test_acceptance_no_official_data_is_na() -> None:
    runs = [_run("hybrid", 1, hm=None), _run("portfolio", 1, hm=None)]
    for run in runs:
        run.counted.clear()
    rows = [(r.strategy, r.criterion, r.status) for r in evaluate_acceptance(runs, max_time_s=100)]
    assert _status(rows, "hard_counted") == "N/A"
    assert _status(rows, "fixed_rules") == "N/A"
    assert _status(rows, "canvis_franja") == "N/A"
    assert _status(rows, "feasibility") == "PASS"


# --- end to end with fakes ----------------------------------------------------


def test_main_writes_results_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def fake_solve(**kwargs: Any) -> SolveExportResult:
        calls.append(kwargs)
        out_csv: Path = kwargs["out_csv"]
        if kwargs["strategy"] == "portfolio" and kwargs["portfolio"].seed == 2:
            return SolveExportResult(False, "phase1 failed: INFEASIBLE blocked A0423 by Jane Doe", out_csv)
        out_csv.write_text("x\n", encoding="utf-8")
        return SolveExportResult(True, "ok phase1=OPTIMAL", out_csv)

    checks: list[dict[str, Any]] = []

    def fake_check(proposal_csv: Path, **kwargs: Any) -> tuple[int, str]:
        checks.append({"csv": proposal_csv, **kwargs})
        return 1, SAMPLE

    monkeypatch.setattr(benchmark, "solve_and_export", fake_solve)
    monkeypatch.setattr(benchmark, "run_official_check", fake_check)
    monkeypatch.setattr(benchmark, "count_placed", lambda _p: 2538)
    monkeypatch.setattr(benchmark, "count_sessions", lambda _p, _s, cursos: 2538 if cursos else 9287)

    name = "pytest_e2e"
    out_dir = REPO_ROOT / "out" / "bench" / name
    try:
        rc = benchmark.main(
            [
                "--paquet",
                str(tmp_path),
                "--semestre",
                "1",
                "--curs",
                "1r",
                "--strategies",
                "hybrid,portfolio",
                "--seeds",
                "1,2",
                "--max-time",
                "60",
                "--out-dir",
                f"out/bench/{name}",
            ]
        )
        assert rc == 0
        assert len(calls) == 4
        assert calls[0]["portfolio"] is None
        assert calls[0]["max_time_s"] == 60
        assert calls[0]["cursos"] == "1r"
        assert calls[3]["portfolio"].seed == 2
        assert calls[3]["out_csv"] == out_dir.resolve() / "portfolio_s2.csv"
        assert len(checks) == 3
        assert checks[0]["semestre"] == 1
        assert checks[0]["timeout_s"] == 900

        with (out_dir / "results.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 4
        assert rows[0]["strategy"] == "hybrid"
        assert rows[0]["R3-AFORAMENT"] == "27"
        assert rows[0]["R5-FALTA"] == "6749"
        assert rows[0]["r5_extra"] == "0"
        assert rows[0]["hores_mortes_min"] == "14520"
        assert rows[0]["sessions"] == "2538"
        failed = rows[3]
        assert failed["ok"] == "False"
        assert failed["status_summary"] == "phase1 failed: INFEASIBLE"
        assert failed["R1-FIXADA"] == ""

        text = (out_dir / "results.csv").read_text(encoding="utf-8") + (out_dir / "summary.md").read_text(
            encoding="utf-8"
        )
        assert "A0423" not in text
        assert "Jane" not in text
        summary = (out_dir / "summary.md").read_text(encoding="utf-8")
        assert "| portfolio |" in summary
        assert "feasibility" in summary
    finally:
        for child in out_dir.glob("*"):
            child.unlink()
        if out_dir.is_dir():
            out_dir.rmdir()


def test_main_no_official_skips_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_solve(**kwargs: Any) -> SolveExportResult:
        kwargs["out_csv"].write_text("x\n", encoding="utf-8")
        return SolveExportResult(True, "ok", kwargs["out_csv"])

    def boom(*_: Any, **__: Any) -> tuple[int, str]:
        raise AssertionError("must not call verifier")

    monkeypatch.setattr(benchmark, "solve_and_export", fake_solve)
    monkeypatch.setattr(benchmark, "run_official_check", boom)
    monkeypatch.setattr(benchmark, "count_placed", lambda _p: 3)
    monkeypatch.setattr(benchmark, "count_sessions", lambda *_a, **_k: 3)

    name = "pytest_noofficial"
    out_dir = REPO_ROOT / "out" / "bench" / name
    try:
        argv = ["--paquet", str(tmp_path), "--semestre", "1", "--strategies", "hybrid", "--seeds", "1"]
        argv += ["--max-time", "5", "--out-dir", f"out/bench/{name}", "--no-official"]
        assert benchmark.main(argv) == 0
        assert (out_dir / "results.csv").is_file()
        assert (out_dir / "summary.md").is_file()
    finally:
        for child in out_dir.glob("*"):
            child.unlink()
        if out_dir.is_dir():
            out_dir.rmdir()
