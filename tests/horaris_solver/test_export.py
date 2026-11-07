from pathlib import Path

from horaris_solver.domain.models import Assignment
from horaris_solver.export.csv_proposta import write_proposta_csv


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
