"""Deprecated MySQL stub — the team DB is SQLite (see sqlite_loader + HORARIS_DB)."""

from __future__ import annotations

from horaris_solver.domain.models import TimetableData


class MysqlTimetableSource:
    def load(self, semestre: int | None = None) -> TimetableData:
        _ = semestre
        raise NotImplementedError(
            "Use SqliteTimetableSource / --db / HORARIS_DB (team schema is SQLite, not MySQL)"
        )
