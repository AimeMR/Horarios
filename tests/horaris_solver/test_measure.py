from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.audit.measure import METRIC_KEYS, is_placeholder_teacher, main, measure
from horaris_solver.domain.models import Activity, Session, TimetableData

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def _load() -> TimetableData:
    return CsvTimetableSource(FIXTURE).load()


def _with_sessions(data: TimetableData, extra: list[Session], activities: list[Activity]) -> TimetableData:
    sessions = dict(data.sessions)
    sessions.update({s.id: s for s in extra})
    acts = dict(data.activities)
    acts.update({a.id: a for a in activities})
    return replace(data, sessions=sessions, activities=acts)


def _activity_for(session: Session) -> Activity:
    return Activity(
        id=session.activity_id,
        code=session.code,
        kind=session.kind,
        session_ids=(session.id,),
        students=session.students,
        turn=session.turn,
        fixed=session.fixed,
        teachers=session.teachers,
        cohorts=session.cohorts,
        duration_min=session.duration_min,
    )


def test_measure_returns_all_keys_as_non_negative_ints() -> None:
    metrics = measure(_load())
    assert tuple(metrics) == METRIC_KEYS
    assert all(type(value) is int and value >= 0 for value in metrics.values())


def test_measure_exact_values_on_mini_paquet() -> None:
    metrics = measure(_load())
    assert metrics["sessions"] == 5
    assert metrics["activities"] == 4
    assert metrics["sessions_without_activity"] == 0
    assert metrics["pinned_activities"] == 1
    assert metrics["movable_activities"] == 3
    assert metrics["heterogeneous_activities"] == 0
    assert metrics["sessions_teachers_1"] == 5
    assert metrics["sessions_teachers_0"] == 0
    assert metrics["partida_conflict_pairs_teacher"] == 0
    assert metrics["partida_conflict_pairs_cohort"] == 0
    assert metrics["teacher_deficit_total"] == 0
    assert metrics["pending_marker_sessions"] == 0


def test_semestre_two_is_empty_on_mini_paquet() -> None:
    metrics = measure(CsvTimetableSource(FIXTURE).load(semestre=2))
    assert all(value == 0 for value in metrics.values())


def test_overlapping_teacher_and_cohort_pair_is_counted() -> None:
    data = _load()
    base = data.sessions["S00003"]  # A2 PAUL/111 GED:1r, Tue 2026-09-14 10:30
    clash = replace(base, id="X1", activity_id="AX", group="PAUL/111", start_min=11 * 60, teachers=frozenset({"D002"}))
    metrics = measure(_with_sessions(data, [clash], [_activity_for(clash)]))
    assert metrics["partida_conflict_pairs_teacher"] == 1
    assert metrics["partida_conflict_pairs_cohort"] == 1
    assert metrics["same_kind_day_pairs_movable_movable"] == 1
    assert metrics["teacher_deficit_subject_kinds"] == 1
    assert metrics["teacher_deficit_total"] == 1


def test_shared_id_pairs_are_excluded() -> None:
    data = _load()
    base = replace(data.sessions["S00003"], shared_id="C1")
    twin = replace(base, id="X1", activity_id="AX")
    data = _with_sessions(data, [base, twin], [_activity_for(twin)])
    metrics = measure(data)
    assert metrics["partida_conflict_pairs_teacher"] == 0
    assert metrics["same_kind_day_pairs_movable_movable"] == 0
    assert metrics["teacher_deficit_total"] == 0


def test_heterogeneous_and_orphan_sessions() -> None:
    data = _load()
    moved = replace(data.sessions["S00002"], start_min=12 * 60)
    orphan = replace(data.sessions["S00004"], id="X9", activity_id="", teachers=frozenset())
    metrics = measure(_with_sessions(data, [moved, orphan], []))
    assert metrics["heterogeneous_activities"] == 1
    assert metrics["sessions_without_activity"] == 1
    assert metrics["sessions_teachers_0"] == 1


def test_mixed_pinned_pair_and_pending_marker() -> None:
    data = _load()
    base = data.sessions["S00005"]  # A4 pinned R7 PLAB
    other = replace(
        base,
        id="X2",
        activity_id="AY",
        fixed="",
        session_date=date(2026, 9, 15),
        start_min=12 * 60,
        teachers=frozenset({"PENDENT-1"}),
    )
    metrics = measure(_with_sessions(data, [other], [_activity_for(other)]))
    assert metrics["same_kind_day_pairs_mixed"] == 1
    assert metrics["pending_marker_sessions"] == 1


@pytest.mark.parametrize("name", ["PENDENT", "pendiente x", "NN", "?", "tbd", "Vacant 2"])
def test_placeholder_detection(name: str) -> None:
    assert is_placeholder_teacher(name)


@pytest.mark.parametrize("name", ["D001", "ANNA", "Gianni"])
def test_real_teacher_not_placeholder(name: str) -> None:
    assert not is_placeholder_teacher(name)


def test_cli_writes_markdown_without_identifiers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "m.md"
    assert main(["--paquet", str(FIXTURE), "--semestre", "1", "--out-md", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "| `sessions` | 5 |" in text
    for identifier in ("D001", "COD1", "Assig1", "S00001", "A1 ", "Q1/"):
        assert identifier not in text
    assert capsys.readouterr().out == text


def test_cli_rejects_bad_curs_and_missing_paquet(tmp_path: Path) -> None:
    assert main(["--paquet", str(FIXTURE), "--curs", "9z"]) == 2
    assert main(["--paquet", str(tmp_path / "nope")]) == 2
