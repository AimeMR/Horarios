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


def _paquet_with_online_activity(tmp_path: Path) -> Path:
    """Copy the mini paquet renaming activity A1 to the online activity A0826."""
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    for source in FIXTURE.iterdir():
        text = source.read_text(encoding="utf-8")
        if source.name == "sessions.csv":
            text = text.replace(",A1,", ",A0826,")
        (paquet / source.name).write_text(text, encoding="utf-8")
    return paquet


def test_a0826_activity_sessions_are_regular(tmp_path: Path) -> None:
    data = CsvTimetableSource(_paquet_with_online_activity(tmp_path)).load()
    for sid in ("S00001", "S00002"):
        assert data.sessions[sid].online is False
        assert data.sessions[sid].sense_espai is False
    assert data.activities["A0826"].sense_espai is False


def test_other_sessions_are_not_online(tmp_path: Path) -> None:
    data = CsvTimetableSource(_paquet_with_online_activity(tmp_path)).load()
    others = [s for s in data.sessions.values() if s.activity_id != "A0826"]
    assert others
    assert all(not s.online and not s.sense_espai for s in others)


def test_mini_paquet_has_no_online_sessions() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    assert not any(s.online for s in data.sessions.values())
