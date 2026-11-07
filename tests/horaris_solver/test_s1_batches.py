"""Failing tests for the S1 morning/afternoon batch runner (T-C)."""

import importlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from horaris_solver.domain.filters import parse_cursos, parse_titulacions
from horaris_solver.domain.models import Session, TimetableData
from horaris_solver.solver.pipeline import SolveExportResult
from horaris_solver.solver.s1_batches import BatchRunReport

_REPO = Path(__file__).resolve().parents[2]
S1_BATCHES_SRC = _REPO / "horaris_solver" / "solver" / "s1_batches.py"
REAL_HORARIS_DB = _REPO / "horaris.db"
MORNING = frozenset({"1r", "2n"})
AFTERNOON = frozenset({"3r", "4t", "M", "?"})
GEET_GEST = frozenset({"GEET", "GEST"})


@dataclass(frozen=True)
class _SolveCall:
    out_csv: Path
    paquet: Path | None
    db: Path | None
    semestre: int | None
    cursos: str | frozenset[str] | None
    titulacions: str | frozenset[str] | None
    max_time_s: int | None
    json_out: Path | None
    strategy: str


class FakeSolve:
    """Injected SolveFn: records kwargs and never touches the real solver."""

    def __init__(
        self,
        *,
        fail_morning_primary: bool = False,
        fail_geet_gest: bool = False,
    ) -> None:
        self.calls: list[_SolveCall] = []
        self._fail_morning_primary = fail_morning_primary
        self._fail_geet_gest = fail_geet_gest

    def __call__(
        self,
        *,
        out_csv: Path,
        paquet: Path | None = None,
        db: Path | None = None,
        semestre: int | None = None,
        cursos: str | frozenset[str] | None = None,
        titulacions: str | frozenset[str] | None = None,
        max_time_s: int | None = None,
        json_out: Path | None = None,
        strategy: str = "hybrid",
    ) -> SolveExportResult:
        self.calls.append(
            _SolveCall(
                out_csv=out_csv,
                paquet=paquet,
                db=db,
                semestre=semestre,
                cursos=cursos,
                titulacions=titulacions,
                max_time_s=max_time_s,
                json_out=json_out,
                strategy=strategy,
            )
        )
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        out_csv.write_text("id_sessio,dia,h_ini,aula\n", encoding="utf-8")
        ok = True
        if self._fail_morning_primary and _is_morning_primary(cursos, titulacions):
            ok = False
        if self._fail_geet_gest and _is_geet_gest_job(cursos, titulacions):
            ok = False
        summary = "INFEASIBLE" if not ok else "ok"
        return SolveExportResult(ok=ok, summary=summary, out_csv=out_csv)


@pytest.fixture(autouse=True)
def _clear_solver_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORARIS_DB", raising=False)
    monkeypatch.delenv("HORARIS_PAQUET", raising=False)


def _s1() -> ModuleType:
    return importlib.import_module("horaris_solver.solver.s1_batches")


def _touch_db(tmp_path: Path) -> Path:
    path = tmp_path / "input.db"
    path.write_bytes(b"")
    return path


def _as_cursos(raw: str | frozenset[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, frozenset):
        return raw
    parsed = parse_cursos(raw)
    return parsed if parsed is not None else frozenset()


def _as_tits(raw: str | frozenset[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, frozenset):
        return frozenset(part.upper() for part in raw)
    parsed = parse_titulacions(str(raw))
    return parsed if parsed is not None else frozenset()


def _is_morning_primary(
    cursos: str | frozenset[str] | None,
    titulacions: str | frozenset[str] | None,
) -> bool:
    return _as_cursos(cursos) == MORNING and not _as_tits(titulacions)


def _is_geet_gest_job(
    cursos: str | frozenset[str] | None,
    titulacions: str | frozenset[str] | None,
) -> bool:
    return _as_cursos(cursos) == frozenset({"2n"}) and GEET_GEST <= _as_tits(titulacions)


def _run(
    tmp_path: Path,
    solve: FakeSolve,
    *,
    db: Path | None = None,
    strategy: str = "hybrid",
    out_dir: Path | None = None,
    conclusions_path: Path | None = None,
) -> BatchRunReport:
    from horaris_solver.solver.s1_batches import run_s1_batches

    return run_s1_batches(
        db=db if db is not None else _touch_db(tmp_path),
        out_dir=out_dir if out_dir is not None else tmp_path / "out",
        conclusions_path=(
            conclusions_path if conclusions_path is not None else tmp_path / "conclusions.md"
        ),
        strategy=strategy,
        max_time_s=1,
        solve=solve,
    )


def _session(sid: str, cohorts: tuple[str, ...]) -> Session:
    return Session(
        id=sid,
        activity_id="A1",
        code="COD",
        kind="TE",
        group="TE/11",
        session_date=date(2026, 9, 14),
        day="L",
        start_min=510,
        duration_min=120,
        students=10,
        room_partida="Q1/1011",
        cohorts=cohorts,
        turn="mati",
        fixed="",
        teachers=frozenset({"D001"}),
    )


def test_default_plan_primaries_are_morning_then_afternoon() -> None:
    mod = _s1()
    assert mod.MORNING_CURS == "1r,2n"
    assert mod.AFTERNOON_CURS == "3r,4t,M,?"
    morning = mod.morning_primary_spec()
    afternoon = mod.afternoon_primary_spec()
    assert _as_cursos(morning.cursos) == MORNING
    assert _as_cursos(afternoon.cursos) == AFTERNOON
    assert morning.role == "primary"
    assert afternoon.role == "primary"
    assert not _as_tits(morning.titulacions)
    assert not _as_tits(afternoon.titulacions)


def test_successful_run_calls_primaries_in_order(tmp_path: Path) -> None:
    solve = FakeSolve()
    _run(tmp_path, solve)
    assert [(_as_cursos(call.cursos), _as_tits(call.titulacions)) for call in solve.calls] == [
        (MORNING, frozenset()),
        (AFTERNOON, frozenset()),
    ]
    assert all(call.semestre == 1 for call in solve.calls)


def test_morning_ladder_specs_include_1r_core_2n_and_geet_gest() -> None:
    mod = _s1()
    available = frozenset({"GEI", "GED", "GEET", "GEST"})
    specs = mod.morning_ladder_specs(available)
    assert any(_as_cursos(spec.cursos) == frozenset({"1r"}) for spec in specs)
    core = [
        spec
        for spec in specs
        if _as_cursos(spec.cursos) == frozenset({"2n"})
        and _as_tits(spec.titulacions)
        and _as_tits(spec.titulacions).isdisjoint(GEET_GEST)
    ]
    assert core, "expected a 2n job whose titulacions exclude GEET/GEST"
    assert _as_tits(core[0].titulacions) <= available - GEET_GEST
    diagnostic = [
        spec
        for spec in specs
        if _as_cursos(spec.cursos) == frozenset({"2n"}) and GEET_GEST <= _as_tits(spec.titulacions)
    ]
    assert len(diagnostic) == 1
    assert diagnostic[0].role == "diagnostic"
    formatted = mod.format_titulacions(GEET_GEST)
    assert {part.strip() for part in formatted.split(",") if part.strip()} == GEET_GEST


def test_joint_morning_failure_runs_ladder_and_afternoon(tmp_path: Path) -> None:
    solve = FakeSolve(fail_morning_primary=True)
    report = _run(tmp_path, solve)
    jobs = [(_as_cursos(call.cursos), _as_tits(call.titulacions)) for call in solve.calls]
    assert jobs[0] == (MORNING, frozenset())
    assert any(cursos == frozenset({"1r"}) for cursos, _tits in jobs[1:])
    assert any(
        cursos == frozenset({"2n"}) and tits.isdisjoint(GEET_GEST) and tits
        for cursos, tits in jobs[1:]
    )
    assert any(cursos == frozenset({"2n"}) and GEET_GEST <= tits for cursos, tits in jobs[1:])
    assert any(cursos == AFTERNOON for cursos, _tits in jobs[1:])
    assert report.used_ladder is True
    assert report.morning_ok is False
    assert report.afternoon_ok is True


def test_geet_gest_failure_writes_conclusions_without_raising(tmp_path: Path) -> None:
    solve = FakeSolve(fail_morning_primary=True, fail_geet_gest=True)
    conclusions = tmp_path / "conclusions.md"
    report = _run(tmp_path, solve, conclusions_path=conclusions)
    assert conclusions.is_file()
    text = conclusions.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "geet" in lowered and "gest" in lowered
    assert any(
        marker in lowered
        for marker in ("fail", "infeasible", "unknown", "false", "not ok")
    )
    assert Path(report.conclusions_path).resolve() == conclusions.resolve()


def test_missing_db_path_raises_value_error(tmp_path: Path) -> None:
    solve = FakeSolve()
    with pytest.raises(ValueError):
        _s1().run_s1_batches(
            db=tmp_path / "missing.db",
            out_dir=tmp_path / "out",
            conclusions_path=tmp_path / "conclusions.md",
            strategy="hybrid",
            max_time_s=1,
            solve=solve,
        )
    assert solve.calls == []


def test_bad_strategy_raises_value_error(tmp_path: Path) -> None:
    solve = FakeSolve()
    with pytest.raises(ValueError):
        _run(tmp_path, solve, strategy="not-a-strategy")
    assert solve.calls == []


def test_out_dir_escape_via_dotdot_raises_value_error(tmp_path: Path) -> None:
    solve = FakeSolve()
    safe = tmp_path / "safe"
    safe.mkdir()
    escape = safe / ".." / "outside"
    with pytest.raises(ValueError):
        _s1().run_s1_batches(
            db=_touch_db(tmp_path),
            out_dir=escape,
            conclusions_path=safe / "conclusions.md",
            strategy="hybrid",
            max_time_s=1,
            solve=solve,
            allowed_root=safe,
        )
    assert solve.calls == []


def test_s1_batches_source_has_no_subprocess_shell_true() -> None:
    if not S1_BATCHES_SRC.is_file():
        with pytest.raises(ImportError):
            importlib.import_module("horaris_solver.solver.s1_batches")
        return
    compact = S1_BATCHES_SRC.read_text(encoding="utf-8").replace(" ", "").replace("\t", "")
    assert "shell=True" not in compact


def test_injected_solve_fn_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid_real_solve(**_kwargs: object) -> SolveExportResult:
        raise AssertionError("injected SolveFn must be used; do not call solve_and_export")

    monkeypatch.setattr(
        "horaris_solver.solver.pipeline.solve_and_export",
        _forbid_real_solve,
    )
    mod = _s1()
    if hasattr(mod, "solve_and_export"):
        monkeypatch.setattr(mod, "solve_and_export", _forbid_real_solve)

    solve = FakeSolve()
    db = _touch_db(tmp_path)
    _run(tmp_path, solve, db=db)
    assert solve.calls, "run_s1_batches must call the injected SolveFn"
    for call in solve.calls:
        assert call.db is not None
        assert Path(call.db).resolve() == db.resolve()
        assert Path(call.db).resolve() != REAL_HORARIS_DB.resolve()
        assert call.semestre == 1
        assert call.strategy == "hybrid"


def test_titulacions_from_data_reads_cohort_prefixes() -> None:
    mod = _s1()
    data = TimetableData(
        sessions={
            "S1": _session("S1", ("GEI:1r", "GEET:2n")),
            "S2": _session("S2", ("GEST:2n",)),
        },
        rooms={},
        activities={},
    )
    assert mod.titulacions_from_data(data) == frozenset({"GEI", "GEET", "GEST"})
