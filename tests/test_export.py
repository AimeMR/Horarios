"""Tests de extractor/export.py: exportar una versión a CSV y validar su nombre.

BD temporal ya migrada con filas inventadas (aules Q1/9001, Q1/9002; assignatura 900001; sessions S90001…S90003).
El caso de ida y vuelta usa la proposta falsa de tests/fixtures/paquet_fals.
"""

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import connect
from extractor.errors import ExportError
from extractor.export import exportar, validar_nom_versio
from extractor.migrate import DIR_MIGRACIONS, pujar

ID_GRUP = "900001·TE/21"
PROPOSTA_FALSA = Path(__file__).resolve().parent / "fixtures" / "paquet_fals" / "proposta_partida.csv"
BOM = b"\xef\xbb\xbf"


def _base(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO assignatura (codi, nom) VALUES ('900001', 'Assignatura Falsa 1')")
    conn.execute(
        "INSERT INTO grup (id_grup, codi, grup, tipus, numero, linia, alumnes_origen, torn_requerit) "
        "VALUES (?, '900001', 'TE/21', 'TE', '21', '21', 'sigma', 'mati')",
        (ID_GRUP,),
    )


def _aules(conn: sqlite3.Connection, *codis: str) -> None:
    for codi in codis:
        conn.execute("INSERT INTO aula (codi) VALUES (?)", (codi,))


def _sessio(conn: sqlite3.Connection, id_sessio: str) -> None:
    conn.execute(
        "INSERT INTO sessio (id_sessio, id_grup, setmana, durada_min, data_partida, dia_partida, h_ini_partida) "
        "VALUES (?, ?, '2027-W03', 60, '2027-01-18', 'L', '08:30')",
        (id_sessio, ID_GRUP),
    )


def _versio(conn: sqlite3.Connection, id_versio: int, nom: str) -> None:
    conn.execute("INSERT INTO versio_horari (id_versio, nom) VALUES (?, ?)", (id_versio, nom))


def _assigna(
    conn: sqlite3.Connection,
    id_versio: int,
    id_sessio: str,
    dia: str,
    h_ini: str,
    aula: str | None,
    data: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data) VALUES (?, ?, ?, ?, ?, ?)",
        (id_versio, id_sessio, dia, h_ini, aula, data),
    )


def _preparar(conn: sqlite3.Connection) -> None:
    """Base común: dos aulas, una asignatura con un grupo, tres sesiones en orden y la versión partida."""
    _base(conn)
    _aules(conn, "Q1/9001", "Q1/9002")
    for id_sessio in ("S90001", "S90002", "S90003"):
        _sessio(conn, id_sessio)
    _versio(conn, 1, "partida")


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connexio = connect(tmp_path / "export.db")
    pujar(connexio, DIR_MIGRACIONS)
    yield connexio
    connexio.close()


# --- contenido del CSV -----------------------------------------------------------------------------------------------


def test_escriu_cabecera_i_una_fila_per_assignacio(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    _assigna(conn, 1, "S90002", "M", "16:00", None)
    _assigna(conn, 1, "S90003", "X", "10:00", "Q1/9002")
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    assert desti.read_text(encoding="utf-8") == (
        "id_sessio,dia,h_ini,aula\nS90001,L,08:30,Q1/9001\nS90002,M,16:00,\nS90003,X,10:00,Q1/9002\n"
    )


def test_retorna_el_nombre_de_filas_escritas(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    _assigna(conn, 1, "S90003", "X", "10:00", "Q1/9002")

    assert exportar(conn, "partida", tmp_path / "partida.csv") == 2


def test_ordena_per_id_sessio_encara_que_s_inserisquin_desordenades(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90003", "X", "10:00", "Q1/9002")
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    _assigna(conn, 1, "S90002", "M", "16:00", "Q1/9001")
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    with desti.open(encoding="utf-8", newline="") as fitxer:
        ids = [fila[0] for fila in csv.reader(fitxer)][1:]
    assert ids == ["S90001", "S90002", "S90003"]


def test_aula_null_es_un_camp_buit(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90002", "M", "16:00", None)
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    with desti.open(encoding="utf-8", newline="") as fitxer:
        filas = list(csv.reader(fitxer))
    assert filas[1] == ["S90002", "M", "16:00", ""]


def test_sense_columna_data_si_cap_fila_la_te(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001", None)
    _assigna(conn, 1, "S90002", "M", "16:00", None, None)
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    assert desti.read_text(encoding="utf-8").splitlines()[0] == "id_sessio,dia,h_ini,aula"


def test_columna_data_si_alguna_fila_la_te_i_buida_a_les_altres(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001", None)
    _assigna(conn, 1, "S90002", "M", "16:00", None, "2027-01-19")
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    assert desti.read_text(encoding="utf-8") == (
        "id_sessio,dia,h_ini,aula,data\nS90001,L,08:30,Q1/9001,\nS90002,M,16:00,,2027-01-19\n"
    )


# --- bytes del fichero -----------------------------------------------------------------------------------------------


def test_fitxer_utf8_sense_bom_amb_crlf_i_salt_final(conn: sqlite3.Connection, tmp_path: Path) -> None:
    # CRLF como los CSV oficiales del paquete (decisión del usuario del 2026-11-07).
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    contingut = desti.read_bytes()
    assert not contingut.startswith(BOM)
    assert contingut.count(b"\n") == contingut.count(b"\r\n")
    assert contingut.endswith(b"\r\n")
    assert contingut.decode("utf-8") == "id_sessio,dia,h_ini,aula\r\nS90001,L,08:30,Q1/9001\r\n"


# --- destino y versiones ---------------------------------------------------------------------------------------------


def test_crea_la_carpeta_pare_del_desti(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    desti = tmp_path / "sortida" / "niu" / "partida.csv"

    exportar(conn, "partida", desti)

    assert desti.is_file()


def test_nomes_exporta_la_versio_demanada(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    _versio(conn, 2, "altra")
    _assigna(conn, 1, "S90001", "L", "08:30", "Q1/9001")
    _assigna(conn, 2, "S90002", "M", "16:00", "Q1/9002")
    _assigna(conn, 2, "S90003", "X", "10:00", "Q1/9002")
    desti = tmp_path / "partida.csv"

    assert exportar(conn, "partida", desti) == 1
    assert desti.read_text(encoding="utf-8") == "id_sessio,dia,h_ini,aula\nS90001,L,08:30,Q1/9001\n"


def test_versio_inexistent_falla_i_no_crea_fitxer(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _preparar(conn)
    desti = tmp_path / "no-existeix.csv"

    with pytest.raises(ExportError):
        exportar(conn, "no-existeix", desti)
    assert not desti.exists()


# --- nombres de versión ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("nom", ["partida", "5.1-aules", "v_2.0", "A", "a" * 64])
def test_validar_nom_accepta_nombres_validos(nom: str) -> None:
    assert validar_nom_versio(nom) == nom


@pytest.mark.parametrize("nom", ["../x", "a b", "", "a" * 65, "x/y", "x;y", "x\\y", "ñu"])
def test_validar_nom_rebutja_nombres_invalids(nom: str) -> None:
    with pytest.raises(ExportError):
        validar_nom_versio(nom)


@pytest.mark.parametrize("nom", ["../x", "a b", "", "a" * 65, "x/y"])
def test_exportar_rebutja_nom_invalid_sense_crear_fitxer(conn: sqlite3.Connection, tmp_path: Path, nom: str) -> None:
    _preparar(conn)
    desti = tmp_path / "sortida.csv"

    with pytest.raises(ExportError):
        exportar(conn, nom, desti)
    assert not desti.exists()


# --- ida y vuelta con la proposta falsa ------------------------------------------------------------------------------


def test_ida_i_tornada_de_la_proposta_falsa_es_identica_byte_a_byte(conn: sqlite3.Connection, tmp_path: Path) -> None:
    with PROPOSTA_FALSA.open(encoding="utf-8", newline="") as fitxer:
        assignacions = list(csv.DictReader(fitxer))
    _base(conn)
    _aules(conn, *sorted({fila["aula"] for fila in assignacions if fila["aula"]}))
    _versio(conn, 1, "partida")
    for fila in assignacions:
        _sessio(conn, fila["id_sessio"])
    for fila in assignacions:
        _assigna(conn, 1, fila["id_sessio"], fila["dia"], fila["h_ini"], fila["aula"] or None)
    desti = tmp_path / "partida.csv"

    exportar(conn, "partida", desti)

    assert desti.read_bytes() == PROPOSTA_FALSA.read_bytes()
