"""GRASP extensions of the greedy: seeded RCL, slot perturbation and Phase 1 team rules (D6/D7)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import Activity, Room, Session, TimetableData
from horaris_solver.solver import greedy_phase1
from horaris_solver.solver.calendar_rules import overlaps
from horaris_solver.solver.conflicts import activities_interact
from horaris_solver.solver.greedy_phase1 import GreedyPerturbation, solve_phase1_greedy
from horaris_solver.solver.phase1_time import Phase1Result
from horaris_solver.solver.rules import Phase1Rules, pool_violations, sibling_pairs, sibling_violations

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"
_MONDAY = date(2026, 9, 14)
_NINE = 9 * 60
_DAY_LETTERS = ("L", "M", "X", "J", "V")


def _spec(
    activity_id: str,
    *,
    code: str | None = None,
    group: str | None = None,
    teacher: str | None = None,
    start: int = _NINE,
    duration: int = 60,
    day_offset: int = 0,
    fixed: str = "",
    kind: str = "TE",
) -> tuple[Session, Activity]:
    """One-session activity with its own teacher and cohort unless told otherwise."""
    code = code or f"C-{activity_id}"
    teachers = frozenset({teacher or f"T-{activity_id}"})
    session = Session(
        id=f"S-{activity_id}",
        activity_id=activity_id,
        code=code,
        kind=kind,
        group=group or f"{kind}/{activity_id}",
        session_date=date(2026, 9, 14 + day_offset),
        day=_DAY_LETTERS[day_offset],
        start_min=start,
        duration_min=duration,
        students=10,
        room_partida="",
        cohorts=(f"COH-{activity_id}",),
        turn="mati",
        fixed=fixed,
        teachers=teachers,
    )
    activity = Activity(
        id=activity_id,
        code=code,
        kind=kind,
        session_ids=(session.id,),
        students=10,
        turn="mati",
        fixed=fixed,
        teachers=teachers,
        cohorts=session.cohorts,
        duration_min=duration,
    )
    return session, activity


def _general_rooms(count: int) -> dict[str, Room]:
    return {f"A{i}": Room(f"A{i}", "A", "Aules docents", 40) for i in range(count)}


def _build(specs: list[tuple[Session, Activity]], rooms: dict[str, Room] | None = None) -> TimetableData:
    return TimetableData(
        sessions={s.id: s for s, _ in specs},
        rooms=rooms or {},
        activities={a.id: a for _, a in specs},
        order=tuple(s.id for s, _ in specs),
    )


def _slack_data() -> TimetableData:
    """Eight independent movable activities: every one has many free slots."""
    return _build([_spec(f"A{i}", day_offset=i % 5) for i in range(8)])


def _rules_data() -> TimetableData:
    """Three siblings (same group/code/kind/week) plus four TE activities competing for one G room."""
    specs = [_spec(f"SIB{i}", code="SIB", group="TE/1") for i in range(3)]
    specs += [_spec(f"P{i}") for i in range(4)]
    specs.append(_spec("PIN", fixed="R1-FIXADA", start=10 * 60))
    return _build(specs, rooms=_general_rooms(3))  # capacity G = 3 - reserve 2 = 1


def _maps(result: Phase1Result) -> tuple[dict[str, str], dict[str, int]]:
    return dict(result.activity_day), dict(result.activity_start)


def _no_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_repair(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", fake_repair)


def _placed_clashes(data: TimetableData, result: Phase1Result) -> list[tuple[str, str]]:
    ids = sorted(result.activity_day)
    hits: list[tuple[str, str]] = []
    for i, left_id in enumerate(ids):
        for right_id in ids[i + 1 :]:
            if result.activity_day[left_id] != result.activity_day[right_id]:
                continue
            left, right = data.activities[left_id], data.activities[right_id]
            if activities_interact(left, right, data) and overlaps(
                result.activity_start[left_id], left.duration_min, result.activity_start[right_id], right.duration_min
            ):
                hits.append((left_id, right_id))
    return hits


# --- GreedyPerturbation -------------------------------------------------------------------------


def test_perturbation_defaults() -> None:
    p = GreedyPerturbation()
    assert (p.rcl_alpha, p.rcl_max, p.weight_jitter, p.top_slots) == (0.15, 8, 0.2, 3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rcl_alpha": 0.0},
        {"rcl_alpha": -0.1},
        {"rcl_alpha": 1.5},
        {"rcl_max": 0},
        {"weight_jitter": -0.01},
        {"weight_jitter": 1.0},
        {"top_slots": 0},
    ],
)
def test_invalid_perturbation_raises(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        GreedyPerturbation(**kwargs)  # type: ignore[arg-type]  # parametrized mix of int/float fields


def test_alpha_one_and_zero_jitter_are_valid() -> None:
    GreedyPerturbation(rcl_alpha=1.0, weight_jitter=0.0, rcl_max=1, top_slots=1)


# --- default path unchanged ---------------------------------------------------------------------


def test_seed_none_matches_current_greedy_on_mini() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    result = solve_phase1_greedy(data, seed=None, rules=None, perturbation=None)
    assert result.status == "GREEDY"
    assert result.objective == 0
    assert result.activity_day == {"A1": "L", "A2": "M", "A3": "L", "A4": "M"}
    assert result.activity_start == {"A1": 510, "A2": 630, "A3": 900, "A4": 510}


def test_perturbation_without_seed_keeps_default_behaviour() -> None:
    data = _slack_data()
    assert _maps(solve_phase1_greedy(data, perturbation=GreedyPerturbation())) == _maps(solve_phase1_greedy(data))


# --- seeded GRASP -------------------------------------------------------------------------------


def test_same_seed_same_result() -> None:
    data = _slack_data()
    first = solve_phase1_greedy(data, seed=7)
    second = solve_phase1_greedy(data, seed=7)
    assert _maps(first) == _maps(second)
    assert first.objective == second.objective


def test_same_seed_same_result_with_rules() -> None:
    data = _rules_data()
    first = solve_phase1_greedy(data, seed=3, rules=Phase1Rules())
    second = solve_phase1_greedy(data, seed=3, rules=Phase1Rules())
    assert _maps(first) == _maps(second)


def test_seed_without_perturbation_uses_defaults() -> None:
    data = _slack_data()
    assert _maps(solve_phase1_greedy(data, seed=11)) == _maps(
        solve_phase1_greedy(data, seed=11, perturbation=GreedyPerturbation())
    )


def test_different_seeds_diversify() -> None:
    data = _slack_data()
    distinct_maps = {
        (tuple(sorted(r.activity_day.items())), tuple(sorted(r.activity_start.items())))
        for r in (solve_phase1_greedy(data, seed=s) for s in range(1, 6))
    }
    assert len(distinct_maps) >= 2


def test_seeded_results_are_complete_and_clash_free() -> None:
    data = _slack_data()
    for seed in range(1, 6):
        result = solve_phase1_greedy(data, seed=seed)
        assert result.ok
        assert set(result.activity_day) == set(data.activities)
        assert _placed_clashes(data, result) == []


def test_seed_does_not_touch_global_random(monkeypatch: pytest.MonkeyPatch) -> None:
    import random

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("global random used")

    for name in ("random", "randrange", "randint", "choice", "uniform", "shuffle", "sample", "seed"):
        monkeypatch.setattr(random, name, forbidden)
    assert solve_phase1_greedy(_slack_data(), seed=5).ok


# --- rules (D6 pools, D7 siblings) --------------------------------------------------------------


def test_rules_instance_violates_without_rules() -> None:
    """Sanity: the instance is only satisfied when rules are enforced."""
    data = _rules_data()
    assert sibling_pairs(data)
    result = solve_phase1_greedy(data)
    assert sibling_violations(data, result.activity_day)
    assert pool_violations(data, result.activity_day, result.activity_start)


@pytest.mark.parametrize("seed", [None, 0, 1, 2, 3, 4, 5])
def test_rules_respected(monkeypatch: pytest.MonkeyPatch, seed: int | None) -> None:
    _no_repair(monkeypatch)
    data = _rules_data()
    result = solve_phase1_greedy(data, seed=seed, rules=Phase1Rules())
    assert result.ok
    assert set(result.activity_day) == set(data.activities)
    assert sibling_violations(data, result.activity_day) == []
    assert pool_violations(data, result.activity_day, result.activity_start) == []
    assert _placed_clashes(data, result) == []


def test_only_same_kind_day_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    data = _rules_data()
    result = solve_phase1_greedy(data, rules=Phase1Rules(same_kind_day=True, room_pools=False))
    assert sibling_violations(data, result.activity_day) == []


def test_only_pool_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    data = _rules_data()
    result = solve_phase1_greedy(data, rules=Phase1Rules(same_kind_day=False, room_pools=True))
    assert pool_violations(data, result.activity_day, result.activity_start) == []


def test_rules_unsatisfiable_leaves_partial_without_violations(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_repair(monkeypatch)
    # Six siblings in one ISO week but only five weekdays: one must stay unplaced.
    data = _build([_spec(f"SIB{i}", code="SIB", group="TE/1") for i in range(6)], rooms=_general_rooms(10))
    result = solve_phase1_greedy(data, seed=1, rules=Phase1Rules())
    assert result.status == "GREEDY_PARTIAL"
    assert len(result.unplaced) == 1
    assert sibling_violations(data, result.activity_day) == []


def test_repair_breaking_rules_is_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _build([_spec(f"SIB{i}", code="SIB", group="TE/1") for i in range(6)], rooms=_general_rooms(10))

    def bad_repair(*_args: Any, **kwargs: Any) -> tuple[dict[str, str], dict[str, int], int]:
        day = dict(kwargs["activity_day"])
        start = dict(kwargs["activity_start"])
        for aid in kwargs["unplaced"]:
            day[aid], start[aid] = "L", _NINE  # lands on a sibling's day
        return day, start, 1

    monkeypatch.setattr(greedy_phase1, "repair_unplaced_with_cpsat", bad_repair)
    result = solve_phase1_greedy(data, rules=Phase1Rules())
    assert result.status == "GREEDY_PARTIAL"
    assert sibling_violations(data, result.activity_day) == []


@pytest.mark.parametrize("seed", [None, *range(10)])
def test_pinned_never_moved(seed: int | None) -> None:
    data = _rules_data()
    result = solve_phase1_greedy(data, seed=seed, rules=Phase1Rules())
    assert (result.activity_day["PIN"], result.activity_start["PIN"]) == ("L", 10 * 60)


@pytest.mark.parametrize("seed", range(10))
def test_pinned_never_moved_without_rules(seed: int) -> None:
    specs = [_spec(f"A{i}", teacher="T") for i in range(4)]
    specs.append(_spec("PIN", teacher="T", fixed="R7-PLAB", kind="PLAB"))
    data = _build(specs)
    result = solve_phase1_greedy(data, seed=seed)
    assert (result.activity_day["PIN"], result.activity_start["PIN"]) == ("L", _NINE)
    assert _placed_clashes(data, result) == []
