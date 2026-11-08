import importlib
import sys
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.check_bridge import default_challenge_root
from horaris_solver.domain.models import DIES, Activity, Assignment, Session, TimetableData, hm
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.score import OfficialMetrics, Score, official_metrics, score_phase1
from horaris_solver.solver.soft_weights import WEIGHT_CANVI_DIA, WEIGHT_HORES_MORTES

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
MONDAY = date(2026, 9, 14)


def _session(
    sid: str,
    group: str,
    start: str,
    duration_min: int = 60,
    *,
    kind: str | None = None,
    day: str = "L",
    cohorts: tuple[str, ...] = ("GED:1r",),
    room: str = "Q1/1011",
    sense_espai: bool = False,
    activity_id: str = "",
) -> Session:
    offset = "LMXJV".index(day)
    return Session(
        id=sid,
        activity_id=activity_id or f"A-{sid}",
        code="C1",
        kind=kind or group.split("/")[0],
        group=group,
        session_date=MONDAY + timedelta(days=offset),
        day=day,
        start_min=hm(start),
        duration_min=duration_min,
        students=10,
        room_partida=room,
        cohorts=cohorts,
        turn="mati",
        fixed="",
        teachers=frozenset({"D1"}),
        sense_espai=sense_espai,
    )


def _data(*sessions: Session) -> TimetableData:
    return TimetableData(sessions={s.id: s for s in sessions}, rooms={}, activities={})


def _partida(data: TimetableData) -> list[Assignment]:
    return [Assignment(s.id, s.day, s.start_min, s.room_partida) for s in data.sessions.values()]


def _metrics(*sessions: Session) -> OfficialMetrics:
    data = _data(*sessions)
    return official_metrics(data, _partida(data))


def test_same_turn_gap_between_theory_and_subgroup_is_counted() -> None:
    metrics = _metrics(_session("S1", "TE/11", "08:30", 120), _session("S2", "PAUL/111", "11:30"))
    assert metrics.hores_mortes_min == 60


def test_gap_across_turns_is_not_counted() -> None:
    metrics = _metrics(_session("S1", "TE/11", "08:30", 120), _session("S2", "TE/11", "15:00"))
    assert metrics.hores_mortes_min == 0


def test_gap_ending_exactly_at_morning_end_is_cross_turn() -> None:
    metrics = _metrics(_session("S1", "TE/11", "13:30"), _session("S2", "TE/11", "15:30"))
    assert metrics.hores_mortes_min == 0


def test_morning_gap_starting_before_turn_end_is_counted() -> None:
    metrics = _metrics(_session("S1", "TE/11", "12:30"), _session("S2", "TE/11", "14:00"))
    assert metrics.hores_mortes_min == 30


def test_theory_of_a_line_is_shared_across_its_subgroups() -> None:
    metrics = _metrics(
        _session("S1", "TE/110", "08:30"),
        _session("S2", "PAUL/111", "11:30"),
        _session("S3", "PAUL/112", "10:30"),
    )
    assert metrics.hores_mortes_min == 120 + 60


def test_gaps_on_different_days_or_cohorts_are_independent() -> None:
    metrics = _metrics(
        _session("S1", "TE/11", "08:30"),
        _session("S2", "TE/11", "12:30", day="M"),
        _session("S3", "TE/11", "12:30", cohorts=("GEI:1r",)),
    )
    assert metrics.hores_mortes_min == 0


def test_session_in_two_cohorts_counts_gap_per_cohort() -> None:
    metrics = _metrics(
        _session("S1", "TE/11", "08:30", cohorts=("GED:1r", "GEI:1r")),
        _session("S2", "TE/12", "10:30", cohorts=("GED:1r", "GEI:1r")),
        _session("S3", "TE/11", "11:30", cohorts=("GED:1r", "GEI:1r")),
    )
    assert metrics.hores_mortes_min == 2 * 120


def test_moved_session_counted_once_even_with_several_cohorts() -> None:
    data = _data(_session("S1", "TE/11", "08:30", cohorts=("GED:1r", "GEI:1r")), _session("S2", "TE/12", "10:30"))
    moved = [Assignment("S1", "X", hm("08:30"), "Q1/1011"), Assignment("S2", "L", hm("10:30"), "Q1/1011")]
    assert official_metrics(data, moved).canvis_franja == 1


def test_start_change_on_same_day_counts_as_slot_change() -> None:
    data = _data(_session("S1", "TE/11", "08:30"))
    assert official_metrics(data, [Assignment("S1", "L", hm("09:30"), "Q1/1011")]).canvis_franja == 1


def test_partida_has_no_changes() -> None:
    metrics = _metrics(_session("S1", "TE/11", "08:30"), _session("S2", "PAUL/111", "10:30"))
    assert (metrics.canvis_franja, metrics.canvis_aula) == (0, 0)


@pytest.mark.parametrize("room", ["Q1/1012", ""])
def test_room_change_from_partida_room_is_counted(room: str) -> None:
    data = _data(_session("S1", "TE/11", "08:30", room="Q1/1011"))
    assert official_metrics(data, [Assignment("S1", "L", hm("08:30"), room)]).canvis_aula == 1


@pytest.mark.parametrize(
    ("partida_room", "sense_espai"),
    [("J/0001", False), ("Q1/1011", True), ("", False)],
    ids=["room-to-move-in", "sense-espai", "no-partida-room"],
)
def test_room_change_not_counted_for_exempt_sessions(partida_room: str, sense_espai: bool) -> None:
    data = _data(_session("S1", "TE/11", "08:30", room=partida_room, sense_espai=sense_espai))
    assert official_metrics(data, [Assignment("S1", "L", hm("08:30"), "Q1/1099")]).canvis_aula == 0


def test_unknown_session_id_is_rejected() -> None:
    data = _data(_session("S1", "TE/11", "08:30"))
    with pytest.raises(ValueError, match="unknown session id"):
        official_metrics(data, [Assignment("NOPE", "L", hm("08:30"), "")])


def test_score_orders_hard_before_unplaced_before_soft() -> None:
    assert Score(0, 5, 10_000, 0, 0) < Score(1, 0, 0, 0, 0)
    assert Score(0, 0, 10_000, 0, 0) < Score(0, 1, 0, 0, 0)
    assert Score(0, 0, 10, 1, 0) < Score(0, 0, 20, 0, 0)
    assert min([Score(2, 0, 0, 0, 0), Score(0, 3, 0, 0, 0), Score(0, 3, 5, 0, 0)]) == Score(0, 3, 0, 0, 0)


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


def test_score_phase1_combines_weighted_metrics_and_unplaced() -> None:
    theory = _session("S1", "TE/11", "08:30", 120, activity_id="A1")
    lab = _session("S2", "PAUL/111", "10:30", activity_id="A2")
    other = _session("S3", "TE/12", "15:00", activity_id="A3")
    data = TimetableData(
        sessions={s.id: s for s in (theory, lab, other)},
        rooms={},
        activities={s.activity_id: _activity(s) for s in (theory, lab, other)},
    )
    result = Phase1Result(True, {"A1": "L", "A2": "L"}, {"A1": hm("08:30"), "A2": hm("11:30")}, "OPTIMAL", "")
    score = score_phase1(data, result, hard_violations=2)
    assert score == Score(
        hard=2,
        unplaced=1,
        soft=WEIGHT_HORES_MORTES * 60 + WEIGHT_CANVI_DIA * 1,
        hores_mortes_min=60,
        canvis_franja=1,
    )


def test_score_phase1_on_partida_of_mini_fixture_has_no_slot_changes() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    templates = {s.activity_id: s for s in data.sessions.values()}
    # Weekday from the date, as the verifier does: S00003 says "M" but its date is a Monday.
    result = Phase1Result(
        True,
        {aid: DIES[templates[aid].session_date.weekday()] for aid in data.activities},
        {aid: templates[aid].start_min for aid in data.activities},
        "OPTIMAL",
        "",
    )
    score = score_phase1(data, result)
    assert (score.hard, score.unplaced, score.canvis_franja) == (0, 0, 0)
    assert score.soft == WEIGHT_HORES_MORTES * score.hores_mortes_min


# Parity with the official verifier: builds its Base from the mini fixture and feeds the same placements.


@pytest.fixture(scope="module")
def verifier() -> Iterator[tuple[ModuleType, ModuleType]]:
    root = default_challenge_root()
    if not (root / "horaris" / "check.py").is_file():
        pytest.skip("repte-horaris-escola not present (symlink or copy the challenge pack)")
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(root))
        yield importlib.import_module("horaris.model"), importlib.import_module("horaris.check")
    for name in list(sys.modules):
        if name == "horaris" or name.startswith("horaris."):
            del sys.modules[name]


def _official_objectives(modules: tuple[ModuleType, ModuleType], assignments: list[Assignment]) -> OfficialMetrics:
    model, check = modules
    base = model.carrega_base(FIXTURE)
    col = {}
    for a in assignments:
        s = base.sessions[a.session_id]
        when = s.data + timedelta(days=model.DIES.index(a.day) - s.data.weekday())
        col[a.session_id] = check.Colocada(s, when, a.start_min, a.room)
    objectives = check._objectius(base, col)
    return OfficialMetrics(objectives["hores_mortes_min"], objectives["canvis_franja"], objectives["canvis_aula"])


def _mini_proposals() -> list[list[Assignment]]:
    data = CsvTimetableSource(FIXTURE).load()
    partida = _partida(data)
    changes = {
        "S00001": Assignment("S00001", "L", hm("08:30"), "Q1/1014"),
        "S00003": Assignment("S00003", "L", hm("11:30"), "Q1/1012"),
        "S00004": Assignment("S00004", "J", hm("16:00"), "Q1/1013"),
    }
    modified = [changes.get(a.session_id, a) for a in partida]
    return [partida, modified]


@pytest.mark.parametrize("index", [0, 1], ids=["partida", "modified"])
def test_metrics_match_official_verifier_on_mini_fixture(
    verifier: tuple[ModuleType, ModuleType],
    index: int,
) -> None:
    assignments = _mini_proposals()[index]
    data = CsvTimetableSource(FIXTURE).load()
    assert official_metrics(data, assignments) == _official_objectives(verifier, assignments)


def test_modified_mini_proposal_hand_computed() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    metrics = official_metrics(data, _mini_proposals()[1])
    # S00001 TE/11 Mon 08:30-10:30 and S00003 PAUL/111 moved to Mon 11:30: 60 min gap for subgroup 111.
    assert metrics == OfficialMetrics(hores_mortes_min=60, canvis_franja=2, canvis_aula=1)
