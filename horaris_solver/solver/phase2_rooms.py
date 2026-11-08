"""Phase 2: assign rooms per session (CP-SAT)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from horaris_solver.domain.models import TIPUS_ORDINARIA, Assignment, Session, TimetableData
from horaris_solver.solver.budget import Deadline
from horaris_solver.solver.calendar_rules import remap_date
from horaris_solver.solver.passadis import passadis
from horaris_solver.solver.room_rules import (
    RESERVA_MIN,
    r1_room_pinned,
    r7_room_pinned,
    room_candidates,
    unit_students,
)
from horaris_solver.soft_weights import WEIGHT_CANVI_AULA, WEIGHT_FORA_PASSADIS, WEIGHT_SIN_AULA

FRANGES = [(8 * 60 + 30) + 60 * i for i in range(13)]
STRICT_R8_SHARE = 0.5
SOFT_R8_SHARE = 0.5  # of the time left after the strict attempt; the partial attempt gets the rest

_clock: Callable[[], float] = time.monotonic


@dataclass(frozen=True)
class Phase2Result:
    ok: bool
    assignments: list[Assignment]
    status: str
    message: str
    r8_relaxed: bool = False
    objective: int = 0
    unassigned: tuple[str, ...] = ()


def _placed_date(session: Session, assignment: Assignment) -> date:
    return remap_date(session.session_date, assignment.day)


def solve_phase2(
    data: TimetableData,
    timed: list[Assignment],
    *,
    max_time_s: float = 150,
    r8_soft_fallback: bool = True,
) -> Phase2Result:
    """Assign rooms: strict R8, then soft R8, then a partial attempt where movable sessions may get no room.

    Strict gets half the budget, soft half of what is left and the partial attempt the rest, so the
    three attempts never exceed ``max_time_s``. Without the fallback, strict gets the whole budget.
    """
    by_id = {a.session_id: a for a in timed}
    deadline = Deadline(max_time_s, clock=_clock)
    strict_s = STRICT_R8_SHARE * max_time_s if r8_soft_fallback else max_time_s
    result = _solve_rooms(data, by_id, max_time_s=strict_s, soft_r8=False)
    if result.ok or not r8_soft_fallback:
        return result
    soft = _solve_rooms(data, by_id, max_time_s=SOFT_R8_SHARE * deadline.remaining(), soft_r8=True)
    if soft.ok:
        return _soft_ok(soft)
    partial = _solve_rooms(data, by_id, max_time_s=deadline.remaining(), soft_r8=True, allow_unassigned=True)
    if not partial.ok:
        return partial
    if not partial.unassigned:
        return _soft_ok(partial)
    return Phase2Result(
        True,
        partial.assignments,
        partial.status,
        f"phase2 partial unassigned={len(partial.unassigned)}",
        True,
        objective=partial.objective,
        unassigned=partial.unassigned,
    )


def _soft_ok(result: Phase2Result) -> Phase2Result:
    return Phase2Result(
        True, result.assignments, result.status, "phase2 ok with R8 soft", True, objective=result.objective
    )


def _solve_rooms(
    data: TimetableData,
    timed: dict[str, Assignment],
    *,
    max_time_s: float,
    soft_r8: bool,
    allow_unassigned: bool = False,
) -> Phase2Result:
    """One CP-SAT room model; ``allow_unassigned`` lets movable sessions take "" at a dominant penalty."""
    model = cp_model.CpModel()
    needing = [s for s in data.sessions.values() if not s.sense_espai]
    unit_load = unit_students(data)
    candidates_of = {s.id: room_candidates(data, s, timed, unit_load) for s in needing}
    # R7 PLABs keep partida rooms outside data.rooms (e.g. J/): index them as ordinary resources.
    external = {c for cands in candidates_of.values() for c in cands if c and c not in data.rooms}
    room_index = {code: i for i, code in enumerate(sorted(set(data.rooms) | external))}
    room_index[""] = len(room_index)
    index_room = {i: code for code, i in room_index.items()}

    session_room: dict[str, cp_model.IntVar] = {}
    placed: dict[str, date] = {s.id: _placed_date(s, timed[s.id]) for s in data.sessions.values() if s.id in timed}
    pinned: set[str] = set()
    # Movable sessions that may be left without room in the partial attempt (True = no room).
    unassigned: dict[str, cp_model.IntVar] = {}

    for session in needing:
        candidates = candidates_of[session.id]
        is_pinned = r7_room_pinned(session, timed) or r1_room_pinned(data, session, timed)
        if not candidates and not (allow_unassigned and not is_pinned):
            return Phase2Result(False, [], "INFEASIBLE", f"no room candidates for {session.id}")
        domain = [room_index[c] for c in candidates]
        if allow_unassigned and not is_pinned and "" not in candidates:
            domain.append(room_index[""])
        session_room[session.id] = model.NewIntVarFromDomain(cp_model.Domain.FromValues(domain), f"room_{session.id}")
        if is_pinned:
            model.Add(session_room[session.id] == room_index[session.room_partida])
            pinned.add(session.id)
        elif len(domain) > len(candidates):
            empty = model.NewBoolVar(f"no_room_{session.id}")
            model.Add(session_room[session.id] == room_index[""]).OnlyEnforceIf(empty)
            model.Add(session_room[session.id] != room_index[""]).OnlyEnforceIf(empty.Not())
            unassigned[session.id] = empty

    # No room double-booking on overlapping sessions same calendar DATE
    sessions_list = needing
    for i, left in enumerate(sessions_list):
        left_a = timed[left.id]
        left_date = placed[left.id]
        for right in sessions_list[i + 1 :]:
            right_a = timed[right.id]
            if left_date != placed[right.id]:
                continue
            if left_a.start_min + left.duration_min <= right_a.start_min:
                continue
            if right_a.start_min + right.duration_min <= left_a.start_min:
                continue
            if left.unit == right.unit:
                model.Add(session_room[left.id] == session_room[right.id])
                continue
            if left.id in pinned and right.id in pinned:
                # Both are constants in their partida room: an overlap is inherited (verifier heretada='fixada').
                continue
            if candidates_of[left.id] == [""] or candidates_of[right.id] == [""]:
                # No room (R7 PLAB without partida room) is not a resource and cannot be double-booked.
                continue
            both_roomed = [unassigned[sid].Not() for sid in (left.id, right.id) if sid in unassigned]
            # Sessions left without room are not a resource: they never clash with each other.
            model.Add(session_room[left.id] != session_room[right.id]).OnlyEnforceIf(both_roomed)

    ordinary = [code for code, room in data.rooms.items() if room.kind == TIPUS_ORDINARIA]
    r8_inherited = 0
    if len(ordinary) >= RESERVA_MIN:
        dates = sorted({placed[s.id] for s in needing})
        for day_date in dates:
            for fringe in FRANGES:
                pinned_rooms = {
                    data.sessions[sid].room_partida
                    for sid in pinned
                    if placed[sid] == day_date
                    and timed[sid].start_min < fringe + 60
                    and timed[sid].start_min + data.sessions[sid].duration_min > fringe
                }
                pinned_used = len(pinned_rooms.intersection(ordinary))
                limit = len(ordinary) - RESERVA_MIN - pinned_used
                if limit < 0:
                    # Inherited excess: pinned sessions alone already exceed the limit.
                    # Movable sessions may not occupy any further ordinary room in this fringe.
                    r8_inherited += 1
                    limit = 0
                occupied_bools: list[cp_model.IntVar] = []
                for room_code in ordinary:
                    used = model.NewBoolVar(f"used_{day_date}_{fringe}_{room_code}")
                    literals: list[cp_model.IntVar] = []
                    for session in needing:
                        if session.id in pinned:
                            continue
                        assignment = timed[session.id]
                        if placed[session.id] != day_date:
                            continue
                        if not (
                            assignment.start_min < fringe + 60 and assignment.start_min + session.duration_min > fringe
                        ):
                            continue
                        lit = model.NewBoolVar(f"occ_{session.id}_{room_code}_{fringe}_{day_date}")
                        eq = session_room[session.id] == room_index[room_code]
                        model.Add(eq).OnlyEnforceIf(lit)
                        model.Add(session_room[session.id] != room_index[room_code]).OnlyEnforceIf(lit.Not())
                        literals.append(lit)
                    if literals:
                        model.AddMaxEquality(used, literals)
                    else:
                        model.Add(used == 0)
                    occupied_bools.append(used)
                if not soft_r8:
                    model.Add(sum(occupied_bools) <= limit)
                else:
                    excess = model.NewIntVar(0, len(ordinary), f"r8_excess_{day_date}_{fringe}")
                    model.Add(sum(occupied_bools) - limit <= excess)
                    soft_terms.append(excess * 50_000)

    soft_terms: list[cp_model.LinearExprT] = [empty * WEIGHT_SIN_AULA for empty in unassigned.values()]

    # Soft: penalize leaving aula_partida
    for session in needing:
        if session.room_partida in room_index and session.room_partida:
            changed = model.NewBoolVar(f"chg_aula_{session.id}")
            model.Add(session_room[session.id] != room_index[session.room_partida]).OnlyEnforceIf(changed)
            model.Add(session_room[session.id] == room_index[session.room_partida]).OnlyEnforceIf(changed.Not())
            soft_terms.append(changed * WEIGHT_CANVI_AULA)

    # Soft: TE↔PAUL consecutive same date — prefer same passadís
    passadis_ids = {code: passadis(code) for code in data.rooms}
    unique_pass = sorted(set(passadis_ids.values()) | {""})
    pass_index = {name: i for i, name in enumerate(unique_pass)}
    room_to_pass = {room_index[code]: pass_index[passadis_ids[code]] for code in data.rooms}
    room_to_pass[room_index[""]] = pass_index[""]

    pass_table = [room_to_pass.get(i, pass_index[""]) for i in range(len(room_index))]
    te_paul_pairs = _te_paul_consecutive_pairs(data, timed, placed)
    for left, right in te_paul_pairs:
        if left.id not in session_room or right.id not in session_room:
            continue
        pass_left = model.NewIntVar(0, len(pass_index) - 1, f"pass_{left.id}_{right.id}_a")
        pass_right = model.NewIntVar(0, len(pass_index) - 1, f"pass_{left.id}_{right.id}_b")
        model.AddElement(session_room[left.id], pass_table, pass_left)
        model.AddElement(session_room[right.id], pass_table, pass_right)
        different = model.NewBoolVar(f"diff_pass_{left.id}_{right.id}")
        model.Add(pass_left != pass_right).OnlyEnforceIf(different)
        model.Add(pass_left == pass_right).OnlyEnforceIf(different.Not())
        soft_terms.append(different * WEIGHT_FORA_PASSADIS)

    if soft_terms:
        model.Minimize(sum(soft_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Phase2Result(False, [], status_name, "phase2 failed", soft_r8)

    out: list[Assignment] = []
    for sid, assignment in timed.items():
        session = data.sessions[sid]
        if session.sense_espai:
            room = ""
        elif sid in session_room:
            room = index_room[solver.Value(session_room[sid])]
        else:
            room = session.room_partida
        out.append(
            Assignment(
                session_id=sid,
                day=assignment.day,
                start_min=assignment.start_min,
                room=room,
            )
        )
    objective = int(solver.ObjectiveValue()) if soft_terms else 0
    message = f"phase2 ok r8_inherited={r8_inherited}" if r8_inherited else "phase2 ok"
    left_out = tuple(sorted(sid for sid, empty in unassigned.items() if solver.Value(empty)))
    return Phase2Result(True, out, status_name, message, soft_r8, objective=objective, unassigned=left_out)


def _te_paul_consecutive_pairs(
    data: TimetableData,
    timed: dict[str, Assignment],
    placed: dict[str, date],
) -> list[tuple[Session, Session]]:
    """TE/PAUL consecutive pairs (same date, shared cohort/line)."""
    by_key: dict[tuple[str, str, date], list[Session]] = {}
    for session in data.sessions.values():
        if session.sense_espai or session.id not in timed:
            continue
        if session.kind not in {"TE", "PAUL"}:
            continue
        day_date = placed[session.id]
        for cohort in session.cohorts:
            key = (cohort, session.line, day_date)
            by_key.setdefault(key, []).append(session)

    pairs: list[tuple[Session, Session]] = []
    seen: set[tuple[str, str]] = set()
    for sessions in by_key.values():
        ordered = sorted(
            {s.id: s for s in sessions}.values(),
            key=lambda s: (timed[s.id].start_min, s.id),
        )
        for left, right in zip(ordered, ordered[1:], strict=False):
            if {left.kind, right.kind} != {"TE", "PAUL"}:
                continue
            a, b = sorted((left.id, right.id))
            pair_key = (a, b)
            if pair_key in seen:
                continue
            seen.add(pair_key)
            pairs.append((left, right))
    return pairs
