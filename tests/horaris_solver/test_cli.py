"""Tests for the horaris-solver CLI `solve` flags (no real solving)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from horaris_solver import cli
from horaris_solver.solver.portfolio import PortfolioConfig


@dataclass(frozen=True)
class _FakeResult:
    ok: bool
    summary: str = "fake summary"


class _Recorder:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(ok=self.ok)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr("horaris_solver.solver.pipeline.solve_and_export", rec)
    return rec


def _solve_argv(tmp_path: Path, *extra: str) -> list[str]:
    return ["solve", "--paquet", str(tmp_path), "--out", str(tmp_path / "out.csv"), *extra]


def test_portfolio_with_all_flags_builds_config(tmp_path: Path, recorder: _Recorder) -> None:
    deficit = tmp_path / "deficit.json"
    argv = _solve_argv(
        tmp_path,
        "--strategy",
        "portfolio",
        "--seed",
        "42",
        "--portfolio-size",
        "8",
        "--top-k",
        "2",
        "--deterministic",
        "--deficit-out",
        str(deficit),
    )
    assert cli.main(argv) == 0
    (call,) = recorder.calls
    assert call["strategy"] == "portfolio"
    assert call["portfolio"] == PortfolioConfig(seed=42, size=8, top_k=2, deterministic=True)
    assert call["deficit_out"] == deficit


def test_portfolio_defaults(tmp_path: Path, recorder: _Recorder) -> None:
    assert cli.main(_solve_argv(tmp_path, "--strategy", "portfolio")) == 0
    (call,) = recorder.calls
    assert call["portfolio"] == PortfolioConfig(seed=0, size=16, top_k=3, deterministic=False)
    assert call["deficit_out"] is None


def test_portfolio_top_k_equal_to_size_is_accepted(tmp_path: Path, recorder: _Recorder) -> None:
    argv = _solve_argv(tmp_path, "--strategy", "portfolio", "--portfolio-size", "3", "--top-k", "3")
    assert cli.main(argv) == 0
    assert recorder.calls[0]["portfolio"] == PortfolioConfig(seed=0, size=3, top_k=3)


def test_small_size_without_top_k_clamps_default_top_k(tmp_path: Path, recorder: _Recorder) -> None:
    argv = _solve_argv(tmp_path, "--strategy", "portfolio", "--portfolio-size", "1")
    assert cli.main(argv) == 0
    assert recorder.calls[0]["portfolio"] == PortfolioConfig(seed=0, size=1, top_k=1)


def test_portfolio_max_time_at_minimum_is_accepted(tmp_path: Path, recorder: _Recorder) -> None:
    assert cli.main(_solve_argv(tmp_path, "--strategy", "portfolio", "--max-time", "20")) == 0
    assert recorder.calls[0]["max_time_s"] == 20


def test_short_max_time_allowed_for_non_portfolio(tmp_path: Path, recorder: _Recorder) -> None:
    assert cli.main(_solve_argv(tmp_path, "--strategy", "hybrid", "--max-time", "5")) == 0
    assert recorder.calls[0]["max_time_s"] == 5


def test_deficit_out_help_mentions_csv(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["solve", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    deficit_help = help_text.rsplit("--deficit-out DEFICIT_OUT", 1)[1].strip()
    assert deficit_help.startswith("Optional CSV report")


def test_hybrid_passes_no_portfolio(tmp_path: Path, recorder: _Recorder) -> None:
    assert cli.main(_solve_argv(tmp_path)) == 0
    (call,) = recorder.calls
    assert call["strategy"] == "hybrid"
    assert call["portfolio"] is None
    assert call["deficit_out"] is None


@pytest.mark.parametrize("strategy", ["hybrid", "greedy", "cpsat"])
def test_deficit_out_forwarded_for_any_strategy(tmp_path: Path, recorder: _Recorder, strategy: str) -> None:
    deficit = tmp_path / "d.json"
    assert cli.main(_solve_argv(tmp_path, "--strategy", strategy, "--deficit-out", str(deficit))) == 0
    (call,) = recorder.calls
    assert call["deficit_out"] == deficit
    assert call["portfolio"] is None


def test_exit_code_follows_result_not_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder(ok=False)
    monkeypatch.setattr("horaris_solver.solver.pipeline.solve_and_export", rec)
    assert cli.main(_solve_argv(tmp_path, "--strategy", "portfolio")) == 1


@pytest.mark.parametrize(
    "extra",
    [
        ["--strategy", "portfolio", "--seed", "-1"],
        ["--strategy", "portfolio", "--seed", "2147483648"],
        ["--strategy", "portfolio", "--seed", "abc"],
        ["--strategy", "portfolio", "--portfolio-size", "0"],
        ["--strategy", "portfolio", "--portfolio-size", "1000000"],
        ["--strategy", "portfolio", "--top-k", "0"],
        ["--strategy", "portfolio", "--top-k", "9"],
        ["--strategy", "portfolio", "--top-k", "5", "--portfolio-size", "3"],
        ["--strategy", "hybrid", "--seed", "1"],
        ["--strategy", "greedy", "--portfolio-size", "4"],
        ["--strategy", "cpsat", "--top-k", "2"],
        ["--deterministic"],
        ["--strategy", "unknown"],
        ["--strategy", "portfolio", "--max-time", "5"],
        ["--strategy", "portfolio", "--max-time", "19"],
    ],
)
def test_abuse_cases_exit_2(tmp_path: Path, recorder: _Recorder, extra: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(_solve_argv(tmp_path, *extra))
    assert exc.value.code == 2
    assert recorder.calls == []
