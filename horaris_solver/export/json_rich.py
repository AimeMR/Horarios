"""Rich JSON export for the React frontend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from horaris_solver.domain.models import ONLINE_ROOM, Assignment, TimetableData, fmt


def build_rich_payload(
    data: TimetableData,
    assignments: list[Assignment],
    *,
    status: str,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_id = {a.session_id: a for a in assignments}
    sessions_out: list[dict[str, Any]] = []
    for sid in data.order:
        session = data.sessions[sid]
        assignment = by_id.get(sid)
        sessions_out.append(
            {
                "id_sessio": sid,
                "activitat_id": session.activity_id,
                "codi": session.code,
                "tipus": session.kind,
                "grup": session.group,
                "dia": assignment.day if assignment else session.day,
                "h_ini": fmt(assignment.start_min if assignment else session.start_min),
                "durada_min": session.duration_min,
                "aula": ONLINE_ROOM if session.online else (assignment.room if assignment else ""),
                "online": session.online,
                "aula_partida": session.room_partida,
                "alumnes": session.students,
                "torn": session.turn,
                "fixada": session.fixed,
                "sense_espai": session.sense_espai,
            }
        )
    return {
        "status": status,
        "metrics": metrics or {},
        "sessions": sessions_out,
        "rooms": [
            {
                "aula": room.code,
                "tipus": room.kind,
                "capacitat": room.capacity,
                "edifici": room.building,
            }
            for room in data.rooms.values()
        ],
    }


def write_rich_json(
    path: Path,
    data: TimetableData,
    assignments: list[Assignment],
    *,
    status: str,
    metrics: dict[str, Any] | None = None,
) -> None:
    payload = build_rich_payload(data, assignments, status=status, metrics=metrics)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
