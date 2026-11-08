"""Invoke the official challenge verifier without rewriting it."""

from __future__ import annotations

import os
import subprocess  # nosec B404 — argv-only official checker bridge
import sys
from pathlib import Path


def default_challenge_root() -> Path:
    # Repo root is parent of the horaris_solver package.
    return Path(__file__).resolve().parents[1] / "repte-horaris-escola"


def run_official_check(
    proposal_csv: Path,
    *,
    semestre: int | None = None,
    challenge_root: Path | None = None,
    paquet: Path | None = None,
    only_rooms: bool = False,
    timeout_s: float = 900.0,
) -> tuple[int, str]:
    root = challenge_root or default_challenge_root()
    if not root.is_dir():
        raise FileNotFoundError(f"challenge root not found: {root}")

    cmd = [sys.executable, "-m", "horaris", "check", str(proposal_csv.resolve())]
    if paquet is not None:
        cmd.extend(["--paquet", str(Path(paquet).resolve())])
    if semestre is not None:
        cmd.extend(["--semestre", str(semestre)])
    if only_rooms:
        cmd.append("--nomes-aules")

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(root) if not existing else f"{root}{os.pathsep}{existing}"

    try:
        completed = subprocess.run(  # noqa: S603  # nosec B603 — argv list only, no shell
            cmd,
            cwd=str(root),
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return 124, f"verifier timeout after {timeout_s:g}s"
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output
