"""Load official paquet CSVs into the domain model."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from horaris_solver.domain.models import (
    Activity,
    CalendarBlock,
    Room,
    Session,
    TimetableData,
    hm,
)


def semestre_de(session_date: date) -> int:
    """Match official verifier: by date, not Sigma T/V field."""
    return 1 if session_date.month >= 9 or session_date.month == 1 else 2


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_teachers(raw: str) -> frozenset[str]:
    parts = [p.strip() for p in (raw or "").split("|") if p.strip()]
    return frozenset(parts)


def _parse_cohorts(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in (raw or "").split("|") if p.strip()]
    return tuple(parts)


class CsvTimetableSource:
    def __init__(self, paquet: Path) -> None:
        self._paquet = Path(paquet)

    def load(self, semestre: int | None = None) -> TimetableData:
        paquet = self._paquet
        rooms = {
            row["aula"]: Room(
                code=row["aula"],
                building=row["edifici"],
                kind=row["tipus"].strip(),
                capacity=int(row["capacitat"]),
                description=(row.get("descripcio") or "").strip(),
            )
            for row in _read_csv(paquet / "aules.csv")
        }

        session_rows = _read_csv(paquet / "sessions.csv")
        with_class = {date.fromisoformat(row["data"]) for row in session_rows}
        free_days: set[date] = set()
        if with_class:
            cursor, last_day = min(with_class), max(with_class)
            while cursor <= last_day:
                if cursor.weekday() < 5 and cursor not in with_class:
                    free_days.add(cursor)
                cursor += timedelta(days=1)

        sessions: dict[str, Session] = {}
        order: list[str] = []
        for row in session_rows:
            session_date = date.fromisoformat(row["data"])
            if semestre is not None and semestre_de(session_date) != semestre:
                continue
            sid = row["id_sessio"]
            sessions[sid] = Session(
                id=sid,
                activity_id=row.get("activitat_id") or "",
                code=row["codi"],
                kind=row["tipus"],
                group=row["grup"],
                session_date=session_date,
                day=row["dia"],
                start_min=hm(row["h_ini"]),
                duration_min=int(row["durada_min"]),
                students=int(row["alumnes"] or 0),
                room_partida=(row.get("aula_partida") or "").strip(),
                cohorts=_parse_cohorts(row.get("titulacions_curs") or ""),
                turn=(row.get("torn_requerit") or "desconegut").strip(),
                fixed=(row.get("fixada") or "").strip(),
                teachers=_parse_teachers(row.get("docents") or ""),
                shared_id=(row.get("id_compartida") or "").strip(),
                sense_espai=(row.get("sense_espai") or "").strip() == "1",
            )
            order.append(sid)

        activities: dict[str, Activity] = {}
        by_activity: dict[str, list[Session]] = {}
        for session in sessions.values():
            if not session.activity_id:
                continue
            by_activity.setdefault(session.activity_id, []).append(session)
        for activity_id, group in by_activity.items():
            first = group[0]
            activities[activity_id] = Activity(
                id=activity_id,
                code=first.code,
                kind=first.kind,
                session_ids=tuple(s.id for s in group),
                students=max(s.students for s in group),
                turn=first.turn,
                fixed=first.fixed,
                teachers=frozenset().union(*(s.teachers for s in group)),
                cohorts=tuple(sorted({c for s in group for c in s.cohorts})),
                duration_min=first.duration_min,
                sense_espai=first.sense_espai,
            )

        calendar: list[CalendarBlock] = []
        calendari_path = paquet / "calendari.csv"
        if calendari_path.exists():
            for row in _read_csv(calendari_path):
                block_date = date.fromisoformat(row["data"])
                start_min = hm(row["h_ini"]) if (row.get("h_ini") or "").strip() else 0
                end_min = hm(row["h_fi"]) if (row.get("h_fi") or "").strip() else 24 * 60
                calendar.append(
                    CalendarBlock(
                        block_date=block_date,
                        start_min=start_min,
                        end_min=end_min,
                        reason=(row.get("motiu") or row.get("tipus") or "").strip(),
                    )
                )

        return TimetableData(
            sessions=sessions,
            rooms=rooms,
            activities=activities,
            calendar=tuple(calendar),
            days_without_class=frozenset(free_days),
            order=tuple(order),
        )
