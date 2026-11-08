import logging
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horaris_solver.api import app as api_app
from horaris_solver.api.app import create_app, resolve_paquet_path
from horaris_solver.solver.pipeline import SolveExportResult
from horaris_solver.solver.portfolio import PortfolioConfig

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_health() -> None:
    client = TestClient(create_app(paquet_roots=[FIXTURE.parent]))
    assert client.get("/health").json()["status"] == "ok"


def test_unknown_job_404() -> None:
    client = TestClient(create_app(paquet_roots=[FIXTURE.parent]))
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_invalid_semestre_422() -> None:
    client = TestClient(create_app(paquet_roots=[FIXTURE.parent]))
    response = client.post(
        "/jobs",
        json={"paquet_path": str(FIXTURE), "semestre": 9},
    )
    assert response.status_code == 422


def test_paquet_outside_allowlist_400(tmp_path: Path) -> None:
    client = TestClient(create_app(paquet_roots=[FIXTURE.parent]))
    response = client.post(
        "/jobs",
        json={"paquet_path": str(tmp_path)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid paquet path"


def test_resolve_paquet_relative_under_root() -> None:
    roots = [FIXTURE.parent.resolve()]
    resolved = resolve_paquet_path("mini_paquet", roots=roots)
    assert resolved == FIXTURE.resolve()


def test_busy_returns_503(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            out_dir=tmp_path / "jobs",
            paquet_roots=[FIXTURE.parent],
            max_jobs=1,
        )
    )
    first = client.post("/jobs", json={"paquet_path": str(FIXTURE), "max_time_s": 60})
    assert first.status_code == 202
    second = client.post("/jobs", json={"paquet_path": str(FIXTURE), "max_time_s": 60})
    assert second.status_code == 503
    assert second.json()["detail"] == "solver busy"


class _RecordingSolve:
    """Stand-in for solve_and_export that records kwargs and signals completion."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.done = threading.Event()

    def __call__(self, **kwargs: Any) -> SolveExportResult:
        self.calls.append(kwargs)
        self.done.set()
        return SolveExportResult(ok=True, summary="ok", out_csv=kwargs["out_csv"])


def _post_and_capture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: dict[str, Any]) -> dict[str, Any]:
    fake = _RecordingSolve()
    monkeypatch.setattr(api_app, "solve_and_export", fake)
    client = TestClient(create_app(out_dir=tmp_path / "jobs", paquet_roots=[FIXTURE.parent]))
    response = client.post("/jobs", json=body)
    assert response.status_code == 202
    assert fake.done.wait(timeout=10)
    assert len(fake.calls) == 1
    return fake.calls[0]


def test_old_request_body_defaults_to_hybrid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    kwargs = _post_and_capture(monkeypatch, tmp_path, {"paquet_path": str(FIXTURE)})
    assert kwargs["strategy"] == "hybrid"
    assert kwargs.get("portfolio") is None
    assert "deficit_out" not in kwargs


@pytest.mark.parametrize("strategy", ["hybrid", "greedy", "cpsat"])
def test_non_portfolio_strategy_forwarded_without_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, strategy: str
) -> None:
    body = {"paquet_path": str(FIXTURE), "strategy": strategy, "seed": 5, "portfolio_size": 4, "top_k": 2}
    kwargs = _post_and_capture(monkeypatch, tmp_path, body)
    assert kwargs["strategy"] == strategy
    assert kwargs.get("portfolio") is None
    assert "deficit_out" not in kwargs


def test_portfolio_request_forwards_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = {
        "paquet_path": str(FIXTURE),
        "strategy": "portfolio",
        "seed": 42,
        "portfolio_size": 8,
        "top_k": 2,
        "max_time_s": 20,
    }
    kwargs = _post_and_capture(monkeypatch, tmp_path, body)
    assert kwargs["strategy"] == "portfolio"
    assert kwargs["portfolio"] == PortfolioConfig(seed=42, size=8, top_k=2)
    assert kwargs["max_time_s"] == 20
    assert "deficit_out" not in kwargs


def test_portfolio_request_without_max_time_uses_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    kwargs = _post_and_capture(monkeypatch, tmp_path, {"paquet_path": str(FIXTURE), "strategy": "portfolio"})
    assert kwargs["portfolio"] == PortfolioConfig(seed=0, size=16, top_k=3)
    assert kwargs["max_time_s"] == api_app.DEFAULT_API_MAX_TIME_S


@pytest.mark.parametrize("strategy", ["hybrid", "greedy", "cpsat"])
def test_top_k_above_size_ignored_for_non_portfolio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, strategy: str
) -> None:
    body = {"paquet_path": str(FIXTURE), "strategy": strategy, "portfolio_size": 2}
    kwargs = _post_and_capture(monkeypatch, tmp_path, body)
    assert kwargs["strategy"] == strategy
    assert kwargs.get("portfolio") is None


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("phase1 failed: INFEASIBLE session S123 activity A9 at C:\\data\\paquet", "phase1 failed: INFEASIBLE"),
        ("phase2 failed", "phase2 failed"),
        ("no sessions after filter", "no sessions after filter"),
        ("/home/user/secret/paquet missing S42", "failed"),
        ("", "failed"),
    ],
)
def test_failure_status_strips_details(summary: str, expected: str) -> None:
    assert api_app.failure_status(summary) == expected


def test_failed_job_log_omits_ids_and_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    summary = "phase1 failed: INFEASIBLE session SESS-777 activity ACT-888 at /srv/secret/paquet"

    def failing_solve(**kwargs: Any) -> SolveExportResult:
        return SolveExportResult(ok=False, summary=summary, out_csv=kwargs["out_csv"])

    monkeypatch.setattr(api_app, "solve_and_export", failing_solve)
    record = api_app.JobRecord(
        id="job1",
        status=api_app.JobStatus.queued,
        created_at="now",
        request=api_app.SolveJobRequest(paquet_path=str(FIXTURE)),
        resolved_paquet=FIXTURE,
    )
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    with caplog.at_level(logging.WARNING, logger=api_app.__name__):
        api_app._run_job(record, tmp_path / "jobs", slots)
    assert record.status == api_app.JobStatus.failed
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "job job1 failed: phase1 failed: INFEASIBLE" in messages
    for leaked in ("SESS-777", "ACT-888", "/srv/secret"):
        assert leaked not in messages


def test_deficit_out_from_client_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = {"paquet_path": str(FIXTURE), "strategy": "portfolio", "deficit_out": str(tmp_path / "x.json")}
    kwargs = _post_and_capture(monkeypatch, tmp_path, body)
    assert "deficit_out" not in kwargs


@pytest.mark.parametrize(
    "extra",
    [
        {"seed": -1},
        {"seed": 2**31},
        {"portfolio_size": 0},
        {"portfolio_size": 65},
        {"top_k": 0},
        {"top_k": 9},
        {"strategy": "portfolio", "portfolio_size": 2, "top_k": 3},
        {"strategy": "unknown"},
        {"strategy": "portfolio", "max_time_s": 10},
        {"strategy": "portfolio", "max_time_s": 19},
    ],
)
def test_invalid_strategy_options_422(monkeypatch: pytest.MonkeyPatch, extra: dict[str, Any]) -> None:
    fake = _RecordingSolve()
    monkeypatch.setattr(api_app, "solve_and_export", fake)
    client = TestClient(create_app(paquet_roots=[FIXTURE.parent]))
    response = client.post("/jobs", json={"paquet_path": str(FIXTURE), **extra})
    assert response.status_code == 422
    assert fake.calls == []
