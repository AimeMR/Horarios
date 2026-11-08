"""Load TimetableData from the team SQLite schema (HORARIS_DB)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from horaris_solver.domain.filters import resolve_turn, session_matches_filters
from horaris_solver.domain.models import (
    Activity,
    CalendarBlock,
    Room,
    Session,
    TimetableData,
    hm,
)


def _parse_teachers(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split("|") if p.strip())


def _parse_cohorts(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(p.strip() for p in raw.split("|") if p.strip())


class SqliteTimetableSource:
    """Read-only loader against Aime's schema (db/migrations/0001_*.sql)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def load(
        self,
        semestre: int | None = None,
        cursos: frozenset[str] | None = None,
        titulacions: frozenset[str] | None = None,
    ) -> TimetableData:
        if not self._db_path.is_file():
            raise FileNotFoundError(f"SQLite DB not found: {self._db_path}")

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            rooms = self._load_rooms(conn)
            sessions, order = self._load_sessions(conn, semestre=semestre, cursos=cursos, titulacions=titulacions)
            activities = self._build_activities(sessions)
            calendar = self._load_calendar(conn)
            # Free days from the full semester calendar, not the curs filter —
            # otherwise days with only other grades look "empty" and freeze remaps.
            free_days = self._days_without_class_from_db(conn, semestre=semestre)
        finally:
            conn.close()

        return TimetableData(
            sessions=sessions,
            rooms=rooms,
            activities=activities,
            calendar=calendar,
            days_without_class=free_days,
            order=tuple(order),
        )

    def _load_rooms(self, conn: sqlite3.Connection) -> dict[str, Room]:
        rows = conn.execute(
            """
            SELECT codi, edifici, tipus, capacitat, descripcio, integrat
            FROM aula
            """
        ).fetchall()
        rooms: dict[str, Room] = {}
        for row in rows:
            desc = (row["descripcio"] or "").strip()
            if int(row["integrat"] or 0) == 1 and "integrat" not in desc.lower():
                desc = (desc + " integrat").strip()
            rooms[row["codi"]] = Room(
                code=row["codi"],
                building=(row["edifici"] or "").strip(),
                kind=(row["tipus"] or "").strip(),
                capacity=int(row["capacitat"] or 0),
                description=desc,
            )
        return rooms

    def _load_sessions(
        self,
        conn: sqlite3.Connection,
        *,
        semestre: int | None,
        cursos: frozenset[str] | None = None,
        titulacions: frozenset[str] | None = None,
    ) -> tuple[dict[str, Session], list[str]]:
        # Cohort list and teachers aggregated per group; session fields from sessio + grup.
        sql = """
            SELECT
                s.id_sessio,
                s.activitat_id,
                COALESCE(s.id_compartida, '') AS id_compartida,
                g.codi,
                g.tipus,
                g.grup,
                s.data_partida,
                s.dia_partida,
                s.h_ini_partida,
                s.durada_min,
                g.alumnes,
                COALESCE(s.aula_partida, '') AS aula_partida,
                g.torn_requerit,
                COALESCE(g.fixada_motiu, '') AS fixada,
                g.sense_espai,
                s.semestre AS semestre,
                (
                    SELECT GROUP_CONCAT(ac.id_cohort, '|')
                    FROM assignatura_cohort ac
                    WHERE ac.codi = g.codi
                ) AS cohorts,
                (
                    SELECT GROUP_CONCAT(d.id_profe, '|')
                    FROM docencia d
                    WHERE d.id_grup = g.id_grup
                      AND (d.vigent_fins IS NULL OR d.vigent_fins >= s.data_partida)
                      AND d.vigent_des_de <= s.data_partida
                ) AS docents
            FROM sessio s
            JOIN grup g ON g.id_grup = s.id_grup
            WHERE (? IS NULL OR s.semestre = ?)
            ORDER BY s.id_sessio
        """
        rows = conn.execute(sql, (semestre, semestre)).fetchall()
        sessions: dict[str, Session] = {}
        order: list[str] = []
        for row in rows:
            cohorts = _parse_cohorts(row["cohorts"])
            if not session_matches_filters(cohorts, cursos=cursos, titulacions=titulacions):
                continue
            explicit_turn = (row["torn_requerit"] or "desconegut").strip()
            sid = row["id_sessio"]
            sessions[sid] = Session(
                id=sid,
                activity_id=(row["activitat_id"] or "").strip(),
                code=row["codi"],
                kind=row["tipus"],
                group=row["grup"],
                session_date=date.fromisoformat(row["data_partida"]),
                day=row["dia_partida"],
                start_min=hm(row["h_ini_partida"]),
                duration_min=int(row["durada_min"]),
                students=int(row["alumnes"] or 0),
                room_partida=(row["aula_partida"] or "").strip(),
                cohorts=cohorts,
                turn=resolve_turn(cohorts, explicit_turn),
                fixed=(row["fixada"] or "").strip(),
                teachers=_parse_teachers(row["docents"]),
                shared_id=(row["id_compartida"] or "").strip(),
                sense_espai=int(row["sense_espai"] or 0) == 1,
            )
            order.append(sid)
        return sessions, order

    def _build_activities(self, sessions: dict[str, Session]) -> dict[str, Activity]:
        by_activity: dict[str, list[Session]] = {}
        for session in sessions.values():
            if not session.activity_id:
                continue
            by_activity.setdefault(session.activity_id, []).append(session)
        activities: dict[str, Activity] = {}
        for activity_id, group in by_activity.items():
            first = group[0]
            cohorts = tuple(sorted({c for s in group for c in s.cohorts}))
            activities[activity_id] = Activity(
                id=activity_id,
                code=first.code,
                kind=first.kind,
                session_ids=tuple(s.id for s in group),
                students=max(s.students for s in group),
                turn=resolve_turn(cohorts, first.turn),
                fixed=first.fixed,
                teachers=frozenset().union(*(s.teachers for s in group)),
                cohorts=cohorts,
                duration_min=first.duration_min,
                sense_espai=first.sense_espai,
            )
        return activities

    def _load_calendar(self, conn: sqlite3.Connection) -> tuple[CalendarBlock, ...]:
        rows = conn.execute(
            """
            SELECT data, h_ini, h_fi, motiu, tipus
            FROM calendari
            ORDER BY data
            """
        ).fetchall()
        blocks: list[CalendarBlock] = []
        for row in rows:
            start = hm(row["h_ini"]) if row["h_ini"] else 0
            end = hm(row["h_fi"]) if row["h_fi"] else 24 * 60
            blocks.append(
                CalendarBlock(
                    block_date=date.fromisoformat(row["data"]),
                    start_min=start,
                    end_min=end,
                    reason=(row["motiu"] or row["tipus"] or "").strip(),
                )
            )
        return tuple(blocks)

    def _days_without_class_from_db(
        self,
        conn: sqlite3.Connection,
        *,
        semestre: int | None,
    ) -> frozenset[date]:
        rows = conn.execute(
            """
            SELECT DISTINCT data_partida
            FROM sessio
            WHERE (? IS NULL OR semestre = ?)
            """,
            (semestre, semestre),
        ).fetchall()
        with_class = {date.fromisoformat(row[0]) for row in rows}
        if not with_class:
            return frozenset()
        free: set[date] = set()
        cursor, last = min(with_class), max(with_class)
        while cursor <= last:
            if cursor.weekday() < 5 and cursor not in with_class:
                free.add(cursor)
            cursor += timedelta(days=1)
        return frozenset(free)
