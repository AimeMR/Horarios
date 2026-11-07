from datetime import date
from pathlib import Path

from horaris_solver.adapters.csv_loader import CsvTimetableSource, semestre_de

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_loads_mini_paquet() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    assert len(data.sessions) == 5
    assert len(data.rooms) == 5
    assert "A1" in data.activities
    assert data.sessions["S00005"].fixed.startswith("R7")


def test_semestre_filter() -> None:
    data = CsvTimetableSource(FIXTURE).load(semestre=1)
    assert data.sessions
    assert all(semestre_de(s.session_date) == 1 for s in data.sessions.values())


def test_semestre_de_matches_official_rule() -> None:
    assert semestre_de(date(2026, 9, 14)) == 1
    assert semestre_de(date(2026, 1, 10)) == 1
    assert semestre_de(date(2027, 2, 1)) == 2
