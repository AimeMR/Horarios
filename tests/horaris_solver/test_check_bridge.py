from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from horaris_solver.check_bridge import run_official_check


def test_timeout_returns_124_with_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)

    code, output = run_official_check(tmp_path / "p.csv", challenge_root=tmp_path, timeout_s=2.5)

    assert code == 124
    assert output == "verifier timeout after 2.5s"


def test_timeout_kwarg_is_forwarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    code, output = run_official_check(tmp_path / "p.csv", challenge_root=tmp_path, timeout_s=42.0)

    assert (code, output) == (0, "ok\n")
    assert seen["timeout"] == 42.0
    assert isinstance(seen["cmd"], list)
    assert "shell" not in seen


def test_default_timeout_is_900(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="bad")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert run_official_check(tmp_path / "p.csv", challenge_root=tmp_path) == (1, "bad")
    assert seen["timeout"] == 900.0


def test_missing_challenge_root_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FileNotFoundError):
        run_official_check(tmp_path / "p.csv", challenge_root=tmp_path / "missing")
