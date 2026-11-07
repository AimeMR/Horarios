from pathlib import Path

from fastapi.testclient import TestClient

from horaris_solver.api.app import create_app, resolve_paquet_path

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
