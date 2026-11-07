"""Ports for timetable data sources."""

from __future__ import annotations

from typing import Protocol

from horaris_solver.domain.models import TimetableData


class TimetableSource(Protocol):
    def load(self, semestre: int | None = None) -> TimetableData:
        """Load timetable data, optionally filtered to one semester."""
