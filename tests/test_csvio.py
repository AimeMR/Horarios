import dataclasses
from pathlib import Path

import pytest

from extractor.csvio import FilaCsv, llegir_csv
from extractor.errors import CargaError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "paquet_fals"

COLUMNES_AULES = ["aula", "edifici", "tipus", "descripcio", "capacitat", "ordinaria"]
COLUMNES_PLANS = ["pla", "titulacions", "descripcio", "fitxer_origen", "data_extraccio"]
COLUMNES_SESSIONS = [
    "id_sessio",
    "activitat_id",
    "id_compartida",
    "codi",
    "assignatura",
    "tipus",
    "grup",
    "semestre",
    "data",
    "setmana",
    "dia",
    "h_ini",
    "h_fi",
    "durada_min",
    "alumnes",
    "capacitat_grup",
    "aula_partida",
    "aules_addicionals_partida",
    "plans",
    "titulacions_curs",
    "dc",
    "torn_requerit",
    "fixada",
    "docents",
    "alumnes_origen",
    "sense_espai",
]
COLUMNES_EXTRA = [c for c in COLUMNES_SESSIONS if c not in ("alumnes_origen", "sense_espai")]
COLUMNES_ACTIVITATS = [
    "activitat_id",
    "codi",
    "grup",
    "semestre",
    "dia",
    "h_ini",
    "h_fi",
    "assignatura",
    "tipus",
    "n_sessions",
    "setmana_primera",
    "setmana_ultima",
    "alumnes",
    "aules_partida",
    "sessions_sense_aula",
    "titulacions_curs",
    "torn_requerit",
    "fixada",
    "docents",
    "sense_espai",
]
COLUMNES_CALENDARI = ["data", "tipus", "h_ini", "h_fi", "motiu", "font"]
COLUMNES_PROPOSTA = ["id_sessio", "dia", "h_ini", "aula"]


@pytest.mark.parametrize(
    ("ruta", "columnes", "files_esperades"),
    [
        (FIXTURES / "aules.csv", COLUMNES_AULES, 7),
        (FIXTURES / "plans.csv", COLUMNES_PLANS, 4),
        (FIXTURES / "sessions.csv", COLUMNES_SESSIONS, 28),
        (FIXTURES / "activitats.csv", COLUMNES_ACTIVITATS, 13),
        (FIXTURES / "calendari.csv", COLUMNES_CALENDARI, 4),
        (FIXTURES / "proposta_partida.csv", COLUMNES_PROPOSTA, 28),
        (FIXTURES / "escenaris" / "grau-nou-40" / "sessions_extra.csv", COLUMNES_EXTRA, 6),
    ],
)
def test_llegeix_cada_fixture_amb_les_seves_columnes(ruta: Path, columnes: list[str], files_esperades: int) -> None:
    files = llegir_csv(ruta, columnes)
    assert len(files) == files_esperades
    assert all(set(columnes) <= set(f.valors) for f in files)


def test_valors_de_fixture_coneguts() -> None:
    aules = llegir_csv(FIXTURES / "aules.csv", COLUMNES_AULES)
    assert aules[0].valors["aula"] == "Q7/7101"
    assert aules[0].valors["capacitat"] == "40"
    assert "integrat" in aules[3].valors["descripcio"].lower()

    plans = llegir_csv(FIXTURES / "plans.csv", COLUMNES_PLANS)
    assert plans[1].valors["descripcio"] == "Grau fictici B i C (pla 9002, 1r i 2n)"
    assert plans[1].valors["titulacions"] == "GFB+GFC"


def test_sessio_sense_aula_i_sense_docents_es_llegeix_com_a_cadena_buida() -> None:
    sessions = llegir_csv(FIXTURES / "sessions.csv", COLUMNES_SESSIONS)
    per_id = {f.valors["id_sessio"]: f for f in sessions}
    assert per_id["S90021"].valors["aula_partida"] == ""
    assert per_id["S90003"].valors["capacitat_grup"] == ""
    assert per_id["S90004"].valors["docents"] == ""


def test_linia_comenca_a_2_i_segueix_el_numero_de_linia_fisica() -> None:
    sessions = llegir_csv(FIXTURES / "sessions.csv", COLUMNES_SESSIONS)
    assert sessions[0].linia == 2
    assert sessions[-1].linia == 29
    assert [f.linia for f in sessions] == list(range(2, 30))


def test_fila_es_frozen_i_valors_son_el_text_tal_cual(tmp_path: Path) -> None:
    ruta = tmp_path / "aules.csv"
    ruta.write_bytes(b"aula,capacitat\n  Q7/7101 , 40 \n")
    fila = llegir_csv(ruta, ["aula", "capacitat"])[0]
    assert fila.valors["aula"] == "  Q7/7101 "
    assert fila.valors["capacitat"] == " 40 "
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(fila, "linia", 99)  # noqa: B010 (asignacion dinamica: comprova que es immutable)


def test_accepta_bom_utf8(tmp_path: Path) -> None:
    contingut = (FIXTURES / "aules.csv").read_bytes()
    ruta = tmp_path / "aules.csv"
    ruta.write_bytes(b"\xef\xbb\xbf" + contingut)
    files = llegir_csv(ruta, COLUMNES_AULES)
    assert len(files) == 7
    assert files[0].valors["aula"] == "Q7/7101"


def test_accepta_columnes_extra_que_no_es_demanen(tmp_path: Path) -> None:
    ruta = tmp_path / "extra.csv"
    ruta.write_bytes(b"aula,nota_interna,capacitat\nQ7/7101,res,40\n")
    fila = llegir_csv(ruta, ["aula", "capacitat"])[0]
    assert fila.valors["aula"] == "Q7/7101"
    assert fila.valors["capacitat"] == "40"


def test_columna_que_falta_en_la_cabecera_falla_a_la_linia_1(tmp_path: Path) -> None:
    ruta = tmp_path / "aules.csv"
    ruta.write_bytes(b"aula,edifici\nQ7/7101,Q7\n")
    with pytest.raises(CargaError) as excinfo:
        llegir_csv(ruta, ["aula", "capacitat"])
    assert excinfo.value.fichero == "aules.csv"
    assert excinfo.value.linia == 1
    assert excinfo.value.columna == "capacitat"
    assert "capacitat" in str(excinfo.value)


def test_columna_que_falta_reporta_la_primera_en_ordre_de_peticio(tmp_path: Path) -> None:
    ruta = tmp_path / "aules.csv"
    ruta.write_bytes(b"aula\nQ7/7101\n")
    with pytest.raises(CargaError) as excinfo:
        llegir_csv(ruta, ["aula", "columna_absent_a", "columna_absent_b"])
    assert excinfo.value.columna == "columna_absent_a"
    assert excinfo.value.linia == 1


def test_fitxer_inexistent_falla_sense_linia_ni_columna(tmp_path: Path) -> None:
    with pytest.raises(CargaError) as excinfo:
        llegir_csv(tmp_path / "no_existeix.csv", ["aula"])
    assert excinfo.value.fichero == "no_existeix.csv"
    assert excinfo.value.linia is None
    assert excinfo.value.columna is None


def test_fila_amb_mes_camps_falla_amb_la_seva_linia(tmp_path: Path) -> None:
    ruta = tmp_path / "sessions.csv"
    ruta.write_bytes(b"a,b\n1,2\n3,4,5\n6,7\n")
    with pytest.raises(CargaError) as excinfo:
        llegir_csv(ruta, ["a", "b"])
    assert excinfo.value.fichero == "sessions.csv"
    assert excinfo.value.linia == 3


def test_fila_amb_menys_camps_falla_amb_la_seva_linia(tmp_path: Path) -> None:
    ruta = tmp_path / "sessions.csv"
    ruta.write_bytes(b"a,b\n1,2\n3\n")
    with pytest.raises(CargaError) as excinfo:
        llegir_csv(ruta, ["a", "b"])
    assert excinfo.value.linia == 3


def test_fitxer_nomes_amb_cabecera_retorna_llista_buida(tmp_path: Path) -> None:
    ruta = tmp_path / "buit.csv"
    ruta.write_bytes(b"aula,capacitat\n")
    assert llegir_csv(ruta, ["aula", "capacitat"]) == []


def test_retorna_filas_csv_frozen_dataclass(tmp_path: Path) -> None:
    ruta = tmp_path / "a.csv"
    ruta.write_bytes(b"a\nx\n")
    fila = llegir_csv(ruta, ["a"])[0]
    assert isinstance(fila, FilaCsv)
    assert fila.linia == 2
    assert dict(fila.valors) == {"a": "x"}
