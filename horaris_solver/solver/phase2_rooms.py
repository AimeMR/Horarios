"""Phase 2: assign rooms per session (CP-SAT)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from horaris_solver.domain.models import TIPUS_ORDINARIA, Assignment, Session, TimetableData
from horaris_solver.solver.calendar_rules import remap_date
from horaris_solver.solver.passadis import passadis
from horaris_solver.solver.soft_weights import WEIGHT_CANVI_AULA, WEIGHT_FORA_PASSADIS

AULA_GENERAL = frozenset({"Aules docents", "Seminaris"})
ESPAI_PRACTIQUES = frozenset({"Laboratoris docents", "Aules informàtiques"})
RESERVA_MIN = 2
FRANGES = [(8 * 60 + 30) + 60 * i for i in range(13)]


@dataclass(frozen=True)
class Phase2Result:
    ok: bool
    assignments: list[Assignment]
    status: str
    message: str
    r8_relaxed: bool = False
    objective: int = 0


def _tipus_permesos(data: TimetableData, session: Session) -> frozenset[str]:
    if session.room_partida in data.rooms:
        kind = data.rooms[session.room_partida].kind
        if kind == "Laboratoris docents" and session.kind != "PLAB":
            return AULA_GENERAL
        return AULA_GENERAL if kind in AULA_GENERAL else frozenset({kind})
    return ESPAI_PRACTIQUES if session.kind == "PLAB" else AULA_GENERAL


def _espai_ok(data: TimetableData, session: Session, room_code: str) -> bool:
    room = data.rooms[room_code]
    if session.kind == "PAUL" and (room.integrated or room.kind == "Aules informàtiques"):
        return True
    return room.kind in _tipus_permesos(data, session)


def _r7_time_unchanged(session: Session, timed: dict[str, Assignment] | None) -> bool:
    if timed is None or session.id not in timed:
        return True
    assignment = timed[session.id]
    return assignment.day == session.day and assignment.start_min == session.start_min


def _candidates(
    data: TimetableData,
    session: Session,
    timed: dict[str, Assignment] | None = None,
) -> list[str]:
    if session.sense_espai:
        return [""]
    if session.kind == "PLAB" and session.fixed.startswith("R7") and not session.room_partida:
        return [""]
    # Keep partida lab only when day/time were not repaired away from partida.
    if (
        session.fixed.startswith("R7")
        and session.room_partida
        and _r7_time_unchanged(session, timed)
    ):
        return [session.room_partida]
    out: list[str] = []
    for room in data.rooms.values():
        if room.capacity < session.students and session.students > 0:
            continue
        if not _espai_ok(data, session, room.code):
            continue
        if room.code.startswith("J/"):
            continue
        out.append(room.code)
    partida = session.room_partida
    if partida and partida in data.rooms and partida not in out:
        if _espai_ok(data, session, partida):
            out.append(partida)
    return out


def _placed_date(session: Session, assignment: Assignment) -> date:
    return remap_date(session.session_date, assignment.day)


def solve_phase2(
    data: TimetableData,
    timed: list[Assignment],
    *,
    max_time_s: int = 150,
    r8_soft_fallback: bool = True,
) -> Phase2Result:
    by_id = {a.session_id: a for a in timed}
    result = _solve_rooms(data, by_id, max_time_s=max_time_s, soft_r8=False)
    if result.ok or not r8_soft_fallback:
        return result
    soft = _solve_rooms(data, by_id, max_time_s=max_time_s, soft_r8=True)
    if soft.ok:
        return Phase2Result(
            True,
            soft.assignments,
            soft.status,
            "phase2 ok with R8 soft",
            True,
            objective=soft.objective,
        )
    return soft


def _solve_rooms(
    data: TimetableData,
    timed: dict[str, Assignment],
    *,
    max_time_s: int,
    soft_r8: bool,
) -> Phase2Result:
    model = cp_model.CpModel()
    room_index = {code: i for i, code in enumerate(sorted(data.rooms))}
    room_index[""] = len(room_index)
    index_room = {i: code for code, i in room_index.items()}

    session_room: dict[str, cp_model.IntVar] = {}
    needing = [s for s in data.sessions.values() if not s.sense_espai]
    placed: dict[str, date] = {
        s.id: _placed_date(s, timed[s.id]) for s in data.sessions.values() if s.id in timed
    }

    for session in needing:
        candidates = _candidates(data, session, timed)
        if not candidates:
            return Phase2Result(False, [], "INFEASIBLE", f"no room candidates for {session.id}")
        domain = [room_index[c] for c in candidates]
        session_room[session.id] = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(domain), f"room_{session.id}"
        )
        if (
            session.fixed.startswith("R7")
            and session.room_partida in room_index
            and _r7_time_unchanged(session, timed)
        ):
            model.Add(session_room[session.id] == room_index[session.room_partida])

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
            model.Add(session_room[left.id] != session_room[right.id])

    ordinary = [code for code, room in data.rooms.items() if room.kind == TIPUS_ORDINARIA]
    if len(ordinary) >= RESERVA_MIN and not soft_r8:
        dates = sorted({placed[s.id] for s in needing})
        for day_date in dates:
            for fringe in FRANGES:
                occupied_bools: list[cp_model.IntVar] = []
                for room_code in ordinary:
                    used = model.NewBoolVar(f"used_{day_date}_{fringe}_{room_code}")
                    literals: list[cp_model.IntVar] = []
                    for session in needing:
                        assignment = timed[session.id]
                        if placed[session.id] != day_date:
                            continue
                        if not (
                            assignment.start_min < fringe + 60
                            and assignment.start_min + session.duration_min > fringe
                        ):
                            continue
                        lit = model.NewBoolVar(
                            f"occ_{session.id}_{room_code}_{fringe}_{day_date}"
                        )
                        eq = session_room[session.id] == room_index[room_code]
                        model.Add(eq).OnlyEnforceIf(lit)
                        model.Add(
                            session_room[session.id] != room_index[room_code]
                        ).OnlyEnforceIf(lit.Not())
                        literals.append(lit)
                    if literals:
                        model.AddMaxEquality(used, literals)
                    else:
                        model.Add(used == 0)
                    occupied_bools.append(used)
                model.Add(sum(occupied_bools) <= len(ordinary) - RESERVA_MIN)

    soft_terms: list[cp_model.LinearExprT] = []

    # Soft: penalize leaving aula_partida
    for session in needing:
        if session.room_partida in room_index and session.room_partida:
            changed = model.NewBoolVar(f"chg_aula_{session.id}")
            model.Add(
                session_room[session.id] != room_index[session.room_partida]
            ).OnlyEnforceIf(changed)
            model.Add(
                session_room[session.id] == room_index[session.room_partida]
            ).OnlyEnforceIf(changed.Not())
            soft_terms.append(changed * WEIGHT_CANVI_AULA)

    # Soft: TE↔PAUL consecutive same date — prefer same passadís
    passadis_ids = {code: passadis(code) for code in data.rooms}
    unique_pass = sorted(set(passadis_ids.values()) | {""})
    pass_index = {name: i for i, name in enumerate(unique_pass)}
    room_to_pass = {
        room_index[code]: pass_index[passadis_ids[code]] for code in data.rooms
    }
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
    solver.parameters.max_time_in_seconds = float(max_time_s)
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
    return Phase2Result(True, out, status_name, "phase2 ok", soft_r8, objective=objective)


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
