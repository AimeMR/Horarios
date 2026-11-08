"""Objective metrics aligned with the official verifier (check.py `_objectius`), used to rank candidates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from horaris_solver.domain.models import MATI, Assignment, Session, TimetableData
from horaris_solver.solver.calendar_rules import remap_date
from horaris_solver.solver.phase1_time import Phase1Result, expand_phase1_to_assignments
from horaris_solver.solver.soft_weights import WEIGHT_CANVI_DIA, WEIGHT_HORES_MORTES

# Rooms outside the teaching block that must be moved in (verifier `AULES_A_TRASLLADAR`).
ROOMS_TO_MOVE_PREFIXES = ("J/",)
THEORY_SUBGROUP = "*"


@dataclass(frozen=True)
class OfficialMetrics:
    hores_mortes_min: int
    canvis_franja: int
    canvis_aula: int


@dataclass(frozen=True, order=True)
class Score:
    hard: int
    unplaced: int
    soft: int
    hores_mortes_min: int
    canvis_franja: int


@dataclass(frozen=True)
class _Placed:
    session: Session
    when: date
    start: int
    room: str

    @property
    def end(self) -> int:
        return self.start + self.session.duration_min


def _room_to_move(room: str) -> bool:
    return bool(room) and room.startswith(ROOMS_TO_MOVE_PREFIXES)


def _place(data: TimetableData, assignments: list[Assignment]) -> list[_Placed]:
    placed: list[_Placed] = []
    for assignment in assignments:
        session = data.sessions.get(assignment.session_id)
        if session is None:
            raise ValueError(f"unknown session id in assignments: {assignment.session_id}")
        when = remap_date(session.session_date, assignment.day)
        placed.append(_Placed(session, when, assignment.start_min, assignment.room))
    return placed


def _slot_changes(placed: list[_Placed]) -> int:
    return sum(1 for p in placed if (p.when, p.start) != (p.session.session_date, p.session.start_min))


def _room_changes(placed: list[_Placed]) -> int:
    return sum(
        1
        for p in placed
        if p.session.room_partida
        and not _room_to_move(p.session.room_partida)
        and not p.session.sense_espai
        and p.room != p.session.room_partida
    )


def _subgroup_agendas(placed: list[_Placed]) -> list[list[_Placed]]:
    """Per (cohort, line, date): each subgroup gets the line's theory plus its own sessions."""
    agenda: dict[tuple[str, str, date, str], list[_Placed]] = defaultdict(list)
    for p in placed:
        subgroup = THEORY_SUBGROUP if p.session.kind == "TE" else p.session.group_number
        for cohort in p.session.cohorts:
            agenda[(cohort, p.session.line, p.when, subgroup)].append(p)
    subgroups: dict[tuple[str, str, date], set[str]] = defaultdict(set)
    for cohort, line, when, subgroup in agenda:
        subgroups[(cohort, line, when)].add(subgroup)
    out: list[list[_Placed]] = []
    for (cohort, line, when), names in subgroups.items():
        theory = agenda.get((cohort, line, when, THEORY_SUBGROUP), [])
        real = [name for name in names if name != THEORY_SUBGROUP]
        if not real:
            out.append(list(theory))
        for name in real:
            out.append(theory + agenda[(cohort, line, when, name)])
    return out


def _dead_minutes(agenda: list[_Placed]) -> int:
    unique = sorted({id(p): p for p in agenda}.values(), key=lambda p: p.start)
    total = 0
    for a, b in zip(unique, unique[1:], strict=False):
        gap = b.start - a.end
        same_turn = (a.end <= MATI[1]) == (b.start < MATI[1])
        if gap > 0 and same_turn:
            total += gap
    return total


def official_metrics(data: TimetableData, assignments: list[Assignment]) -> OfficialMetrics:
    placed = _place(data, assignments)
    return OfficialMetrics(
        hores_mortes_min=sum(_dead_minutes(agenda) for agenda in _subgroup_agendas(placed)),
        canvis_franja=_slot_changes(placed),
        canvis_aula=_room_changes(placed),
    )


def score_phase1(data: TimetableData, result: Phase1Result, *, hard_violations: int = 0) -> Score:
    metrics = official_metrics(data, expand_phase1_to_assignments(data, result))
    unplaced = sum(1 for aid in data.activities if aid not in result.activity_day or aid not in result.activity_start)
    soft = WEIGHT_HORES_MORTES * metrics.hores_mortes_min + WEIGHT_CANVI_DIA * metrics.canvis_franja
    return Score(
        hard=hard_violations,
        unplaced=unplaced,
        soft=soft,
        hores_mortes_min=metrics.hores_mortes_min,
        canvis_franja=metrics.canvis_franja,
    )
