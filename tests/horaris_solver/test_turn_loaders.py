"""Loaders must honour explicit grup.torn_requerit via resolve_turn."""

from __future__ import annotations

import csv
import inspect
import shutil
from pathlib import Path

from horaris_solver.adapters import csv_loader, sqlite_loader
from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.filters import resolve_turn

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def _copy_mini_paquet(tmp_path: Path) -> Path:
    dest = tmp_path / "mini_paquet"
    shutil.copytree(FIXTURE, dest)
    return dest


def _set_session_turns(sessions_csv: Path, session_ids: frozenset[str], turn: str) -> None:
    with sessions_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise AssertionError("sessions.csv has no header")
        rows = list(reader)
    for row in rows:
        if row["id_sessio"] in session_ids:
            row["torn_requerit"] = turn
    with sessions_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_csv_loader_keeps_explicit_tarda_on_first_year(tmp_path: Path) -> None:
    paquet = _copy_mini_paquet(tmp_path)
    _set_session_turns(paquet / "sessions.csv", frozenset({"S00001", "S00002"}), "tarda")
    data = CsvTimetableSource(paquet).load()
    session = data.sessions["S00001"]
    activity = data.activities["A1"]
    assert session.cohorts == ("GED:1r",)
    assert session.turn == "tarda"
    assert activity.turn == "tarda"
    assert activity.turn == resolve_turn(session.cohorts, "tarda")
    assert resolve_turn(("GEI:1r",), "tarda") == "tarda"


def test_csv_and_sqlite_loaders_use_resolve_turn() -> None:
    assert "resolve_turn" in inspect.getsource(csv_loader)
    assert "resolve_turn" in inspect.getsource(sqlite_loader)
