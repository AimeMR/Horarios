"""Thin async job API (no auth in v1 — bind to localhost only)."""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from horaris_solver.solver.budget import PORTFOLIO_MIN_TOTAL_S
from horaris_solver.solver.pipeline import solve_and_export
from horaris_solver.solver.portfolio import PortfolioConfig

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_JOBS = 1
DEFAULT_API_MAX_TIME_S = 300
_FAILURE_STATUS = re.compile(r"^(no sessions after filter|portfolio needs|phase\d failed(?:: [A-Z_]+)?)")


def failure_status(summary: str) -> str:
    """Short, id- and path-free status for server logs."""
    match = _FAILURE_STATUS.match(summary)
    return match.group(1) if match else "failed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class SolveJobRequest(BaseModel):
    paquet_path: str = Field(..., min_length=1, max_length=512)
    semestre: int | None = None
    max_time_s: int | None = Field(default=None, ge=1, le=3600)
    strategy: Literal["hybrid", "greedy", "cpsat", "portfolio"] = "hybrid"
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    portfolio_size: int = Field(default=16, ge=1, le=64)
    top_k: int = Field(default=3, ge=1, le=8)

    @field_validator("semestre")
    @classmethod
    def _semestre_ok(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value not in (1, 2):
            raise ValueError("semestre must be 1 or 2")
        return value

    @model_validator(mode="after")
    def _strategy_options_ok(self) -> Self:
        if self.strategy != "portfolio":
            return self
        if self.top_k > self.portfolio_size:
            raise ValueError("top_k must be <= portfolio_size")
        if self.max_time_s is not None and self.max_time_s < PORTFOLIO_MIN_TOTAL_S:
            raise ValueError(f"max_time_s must be >= {PORTFOLIO_MIN_TOTAL_S:g} for the portfolio strategy")
        return self

    def portfolio_config(self) -> PortfolioConfig | None:
        if self.strategy != "portfolio":
            return None
        return PortfolioConfig(seed=self.seed, size=self.portfolio_size, top_k=self.top_k)


@dataclass
class JobRecord:
    id: str
    status: JobStatus
    created_at: str
    request: SolveJobRequest
    resolved_paquet: Path
    summary: str = ""
    error: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def _default_paquet_roots() -> list[Path]:
    # app.py → api → horaris_solver → repo root
    repo = Path(__file__).resolve().parents[2]
    return [
        (repo / "tests" / "horaris_solver" / "fixtures").resolve(),
        (repo / "repte-horaris-escola").resolve(),
    ]


def paquet_roots_from_env() -> list[Path]:
    raw = os.environ.get("PAQUET_ROOT", "").strip()
    if not raw:
        return _default_paquet_roots()
    roots: list[Path] = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            roots.append(Path(part).expanduser().resolve())
    return roots or _default_paquet_roots()


def resolve_paquet_path(raw: str, roots: list[Path] | None = None) -> Path:
    """Resolve a client path and require it under an allowlisted root."""
    allowed = roots if roots is not None else paquet_roots_from_env()
    if not allowed:
        raise ValueError("no paquet roots configured")

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        # Relative paths are tried under each root (first match that exists wins for resolve check).
        resolved_candidates = [(root / candidate).resolve() for root in allowed]
    else:
        resolved_candidates = [candidate.resolve()]

    for resolved in resolved_candidates:
        for root in allowed:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_dir():
                return resolved
            raise ValueError("paquet path must be an existing directory")
    raise ValueError("paquet path outside allowlisted roots")


def max_concurrent_jobs() -> int:
    raw = os.environ.get("SOLVER_MAX_CONCURRENT_JOBS", str(DEFAULT_MAX_CONCURRENT_JOBS))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("SOLVER_MAX_CONCURRENT_JOBS must be an integer") from exc
    if value < 1:
        raise ValueError("SOLVER_MAX_CONCURRENT_JOBS must be >= 1")
    return value


def create_app(
    *,
    out_dir: Path | None = None,
    paquet_roots: list[Path] | None = None,
    max_jobs: int | None = None,
) -> FastAPI:
    output_root = (out_dir or Path("out/jobs")).resolve()
    configured = paquet_roots if paquet_roots is not None else paquet_roots_from_env()
    roots = [p.resolve() for p in configured]
    limit = max_jobs if max_jobs is not None else max_concurrent_jobs()
    slots = threading.BoundedSemaphore(limit)
    jobs: dict[str, JobRecord] = {}
    jobs_lock = threading.Lock()

    app = FastAPI(title="horaris-solver", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/jobs", status_code=202)
    def create_job(body: SolveJobRequest) -> dict[str, Any]:
        try:
            resolved = resolve_paquet_path(body.paquet_path, roots=roots)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid paquet path") from None

        if not slots.acquire(blocking=False):
            raise HTTPException(status_code=503, detail="solver busy")

        job_id = uuid.uuid4().hex
        record = JobRecord(
            id=job_id,
            status=JobStatus.queued,
            created_at=datetime.now(UTC).isoformat(),
            request=body,
            resolved_paquet=resolved,
        )
        with jobs_lock:
            jobs[job_id] = record

        thread = threading.Thread(
            target=_run_job,
            args=(record, output_root, slots),
            daemon=True,
            name=f"solve-{job_id[:8]}",
        )
        thread.start()
        return {"job_id": job_id, "status": record.status.value}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        record = _get(jobs, jobs_lock, job_id)
        return {
            "job_id": record.id,
            "status": record.status.value,
            "created_at": record.created_at,
            "summary": record.summary,
            "error": record.error,
        }

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str) -> dict[str, Any]:
        record = _get(jobs, jobs_lock, job_id)
        if record.status == JobStatus.failed:
            raise HTTPException(status_code=409, detail="job failed")
        if record.status != JobStatus.done:
            raise HTTPException(status_code=409, detail="job not finished")
        return {
            "job_id": record.id,
            "status": record.status.value,
            "csv_file": "proposta.csv",
            "json_file": "proposta.json",
            "summary": record.summary,
        }

    return app


def _get(jobs: dict[str, JobRecord], jobs_lock: threading.Lock, job_id: str) -> JobRecord:
    with jobs_lock:
        record = jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return record


def _run_job(record: JobRecord, output_root: Path, slots: threading.BoundedSemaphore) -> None:
    with record.lock:
        record.status = JobStatus.running
    try:
        job_dir = output_root / record.id
        job_dir.mkdir(parents=True, exist_ok=True)
        out_csv = job_dir / "proposta.csv"
        out_json = job_dir / "proposta.json"
        max_time = record.request.max_time_s
        if max_time is None:
            max_time = DEFAULT_API_MAX_TIME_S
        result = solve_and_export(
            paquet=record.resolved_paquet,
            out_csv=out_csv,
            semestre=record.request.semestre,
            max_time_s=max_time,
            json_out=out_json,
            strategy=record.request.strategy,
            portfolio=record.request.portfolio_config(),
        )
        with record.lock:
            if result.ok:
                record.summary = f"ok sessions exported r8_relaxed={result.r8_relaxed}"
                record.status = JobStatus.done
            else:
                record.summary = "solve failed"
                record.error = "solve failed"
                record.status = JobStatus.failed
                logger.warning("job %s failed: %s", record.id, failure_status(result.summary))
    except Exception:
        logger.exception("job %s crashed", record.id)
        with record.lock:
            record.status = JobStatus.failed
            record.error = "job failed"
            record.summary = "job failed"
    finally:
        slots.release()
