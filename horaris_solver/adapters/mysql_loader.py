"""Deprecated — the team DB is SQLite. Use sqlite_loader + --db / HORARIS_DB."""

from __future__ import annotations

from horaris_solver.domain.models import TimetableData


class MysqlTimetableSource:
    def load(
        self,
        semestre: int | None = None,
        cursos: frozenset[str] | None = None,
        titulacions: frozenset[str] | None = None,
    ) -> TimetableData:
        _ = (semestre, cursos, titulacions)
        raise NotImplementedError("Use SqliteTimetableSource (--db / HORARIS_DB), not MySQL")
