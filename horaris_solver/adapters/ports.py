"""Ports for timetable data sources."""

from __future__ import annotations

from typing import Protocol

from horaris_solver.domain.models import TimetableData


class TimetableSource(Protocol):
    def load(
        self,
        semestre: int | None = None,
        cursos: frozenset[str] | None = None,
        titulacions: frozenset[str] | None = None,
    ) -> TimetableData:
        """Load timetable data, optionally filtered by semester, grades, degrees."""
