"""Cohort clash predicates must match the audit helper, including TE lines."""

import inspect
from datetime import date

import pytest

from horaris_solver.audit import cohort_clashes as audit_mod
from horaris_solver.audit.cohort_clashes import _groups_clash
from horaris_solver.domain.models import Activity, Session, TimetableData
from horaris_solver.solver.conflicts import activities_interact, cohort_clash


def _session(
    sid: str,
    *,
    kind: str,
    group: str,
    cohorts: tuple[str, ...] = ("GEI:1r",),
    teachers: frozenset[str] = frozenset({"D001"}),
    shared_id: str = "",
    activity_id: str | None = None,
    code: str | None = None,
) -> Session:
    return Session(
        id=sid,
        activity_id=activity_id or f"A{sid}",
        code=code if code is not None else sid,
        kind=kind,
        group=group,
        session_date=date(2026, 9, 14),
        day="L",
        start_min=510,
        duration_min=120,
        students=20,
        room_partida="",
        cohorts=cohorts,
        turn="mati",
        fixed="",
        teachers=teachers,
        shared_id=shared_id,
    )


def _activity(session: Session) -> Activity:
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


def _data(*sessions: Session) -> TimetableData:
    return TimetableData(
        sessions={session.id: session for session in sessions},
        rooms={},
        activities={session.activity_id: _activity(session) for session in sessions},
    )


def test_te_line_31_clashes_with_te_310() -> None:
    left = _session("S31", kind="TE", group="TE/31", teachers=frozenset({"D031"}))
    right = _session("S310", kind="TE", group="TE/310", teachers=frozenset({"D310"}))
    assert left.line == "31"
    assert right.line == "31"
    assert left.group_number != right.group_number
    data = _data(left, right)
    left_act = data.activities[left.activity_id]
    right_act = data.activities[right.activity_id]
    assert _groups_clash(left, right) is True
    assert cohort_clash(left_act, right_act, data) is True
    assert activities_interact(left_act, right_act, data) is True


@pytest.mark.parametrize(
    ("left_kind", "left_group", "right_kind", "right_group", "expected"),
    [
        ("TE", "TE/31", "TE", "TE/310", True),
        ("TE", "TE/31", "TE", "TE/32", False),
        ("TE", "TE/31", "PAUL", "PAUL/31", True),
        ("PAUL", "PAUL/111", "PAUL", "PAUL/111", True),
        ("PAUL", "PAUL/111", "PAUL", "PAUL/211", False),
        ("TE", "TE/31", "PLAB", "PLAB/320", False),
    ],
)
def test_cohort_clash_agrees_with_groups_clash(
    left_kind: str,
    left_group: str,
    right_kind: str,
    right_group: str,
    expected: bool,
) -> None:
    left = _session("SL", kind=left_kind, group=left_group, teachers=frozenset({"DL"}))
    right = _session("SR", kind=right_kind, group=right_group, teachers=frozenset({"DR"}))
    data = _data(left, right)
    left_act = data.activities[left.activity_id]
    right_act = data.activities[right.activity_id]
    assert _groups_clash(left, right) is expected
    assert cohort_clash(left_act, right_act, data) is expected
    assert activities_interact(left_act, right_act, data) is expected


def test_disjoint_cohorts_do_not_clash() -> None:
    left = _session(
        "S1",
        kind="TE",
        group="TE/31",
        cohorts=("GEI:1r",),
        teachers=frozenset({"DL"}),
    )
    right = _session(
        "S2",
        kind="TE",
        group="TE/310",
        cohorts=("GEET:1r",),
        teachers=frozenset({"DR"}),
    )
    data = _data(left, right)
    assert _groups_clash(left, right) is False
    assert cohort_clash(data.activities["AS1"], data.activities["AS2"], data) is False
    assert activities_interact(data.activities["AS1"], data.activities["AS2"], data) is False


def test_shared_teaching_event_does_not_interact() -> None:
    left = _session("S1", kind="TE", group="TE/31", shared_id="SH1", teachers=frozenset({"DL"}))
    right = _session("S2", kind="TE", group="TE/310", shared_id="SH1", teachers=frozenset({"DR"}))
    data = _data(left, right)
    assert _groups_clash(left, right) is True
    assert activities_interact(data.activities["AS1"], data.activities["AS2"], data) is False


def test_cohort_clash_missing_session_raises() -> None:
    left = _session("S1", kind="TE", group="TE/31")
    right = _session("S2", kind="TE", group="TE/310")
    data = TimetableData(sessions={}, rooms={}, activities={})
    with pytest.raises(KeyError):
        cohort_clash(_activity(left), _activity(right), data)


def test_audit_uses_conflicts_predicates() -> None:
    source = inspect.getsource(audit_mod)
    assert "horaris_solver.solver.conflicts" in source
