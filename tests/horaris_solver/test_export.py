from dataclasses import replace
from pathlib import Path

import pytest

from horaris_solver.adapters.csv_loader import CsvTimetableSource
from horaris_solver.domain.models import ONLINE_ROOM, Assignment
from horaris_solver.export.csv_proposta import read_proposta_csv, write_proposta_csv
from horaris_solver.export.json_rich import build_rich_payload

FIXTURE = Path(__file__).parent / "fixtures" / "mini_paquet"


def test_write_proposta_csv(tmp_path: Path) -> None:
    path = tmp_path / "proposta.csv"
    write_proposta_csv(
        path,
        [
            Assignment(session_id="S00002", day="M", start_min=510, room="Q1/1011"),
            Assignment(session_id="S00001", day="L", start_min=540, room="Q1/1012"),
        ],
        order=("S00001", "S00002"),
    )
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert lines[0] == "id_sessio,dia,h_ini,aula"
    assert lines[1].startswith("S00001,L,09:00,")


def test_online_session_written_as_online_and_read_back(tmp_path: Path) -> None:
    path = tmp_path / "proposta.csv"
    rows = [
        Assignment(session_id="S00001", day="L", start_min=540, room=""),
        Assignment(session_id="S00002", day="M", start_min=510, room="Q1/1011"),
    ]
    write_proposta_csv(path, rows, online_ids=frozenset({"S00001"}))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[1] == "S00001,L,09:00,ONLINE"
    assert lines[2] == "S00002,M,08:30,Q1/1011"
    back = {a.session_id: a for a in read_proposta_csv(path)}
    assert back["S00001"].room == ONLINE_ROOM
    assert back["S00002"].room == "Q1/1011"


def test_write_without_online_ids_keeps_rooms(tmp_path: Path) -> None:
    path = tmp_path / "proposta.csv"
    write_proposta_csv(path, [Assignment(session_id="S00001", day="L", start_min=540, room="")])
    assert path.read_text(encoding="utf-8").strip().splitlines()[1] == "S00001,L,09:00,"


def test_read_rejects_short_rows(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("id_sessio,dia,h_ini,aula\nS00001,L\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        read_proposta_csv(path)


def test_rich_json_shows_online_room() -> None:
    data = CsvTimetableSource(FIXTURE).load()
    online = replace(data.sessions["S00001"], online=True, sense_espai=True)
    data = replace(data, sessions={**data.sessions, "S00001": online})
    assignments = [Assignment(sid, s.day, s.start_min, "") for sid, s in data.sessions.items()]
    payload = build_rich_payload(data, assignments, status="ok")
    by_id = {row["id_sessio"]: row for row in payload["sessions"]}
    assert by_id["S00001"]["aula"] == ONLINE_ROOM and by_id["S00001"]["online"] is True
    assert by_id["S00002"]["aula"] == "" and by_id["S00002"]["online"] is False
