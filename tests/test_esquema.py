"""Tests del esquema que crea db/migrations/0001_esquema_inicial sobre una BD temporal ya migrada.

Datos inventados: códigos 900001, S90001, D901, GF9 y aula Q1/9001.
"""

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import connect
from extractor.migrate import DIR_MIGRACIONS, baixar, descobrir, pujar

TAULES_USUARI = [
    "activitat",
    "aula",
    "assignacio",
    "assignatura",
    "assignatura_cohort",
    "assignatura_pla",
    "calendari",
    "cancellacio",
    "canvi_alumnes",
    "cohort",
    "departament",
    "docencia",
    "escenari",
    "facultat",
    "grup",
    "indisponibilitat_profe",
    "pla_estudis",
    "pla_titulacio",
    "profe",
    "registre_canvi",
    "relaxacio",
    "relaxacio_sessio",
    "sessio",
    "tancament_aula",
    "titulacio",
    "versio_horari",
]
TAULES_ESPERADES = sorted([*TAULES_USUARI, "schema_migrations"])
ID_GRUP = "900001·TE/21"


def _taules(conn: sqlite3.Connection) -> list[str]:
    files = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(fila[0]) for fila in files]


def _indexos(conn: sqlite3.Connection) -> list[str]:
    files = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(fila[0]) for fila in files]


def _columnes_index(conn: sqlite3.Connection, index: str) -> list[str]:
    files = conn.execute(f"PRAGMA index_info('{index}')").fetchall()
    return [str(fila[2]) for fila in files]


def _base(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO assignatura (codi, nom) VALUES ('900001', 'Assignatura Falsa 1')")


def _afegeix_grup(conn: sqlite3.Connection, torn: str | None) -> None:
    conn.execute(
        "INSERT INTO grup (id_grup, codi, grup, tipus, numero, linia, alumnes_origen, torn_requerit) "
        "VALUES (?, '900001', 'TE/21', 'TE', '21', '21', 'sigma', ?)",
        (ID_GRUP, torn),
    )


def _preparar_grup(conn: sqlite3.Connection, torn: str | None = "mati") -> None:
    _base(conn)
    _afegeix_grup(conn, torn)


def _afegeix_sessio(conn: sqlite3.Connection, id_sessio: str, data: str) -> None:
    conn.execute(
        "INSERT INTO sessio (id_sessio, id_grup, setmana, durada_min, data_partida, dia_partida, h_ini_partida) "
        "VALUES (?, ?, '2027-W03', 60, ?, 'L', '08:30')",
        (id_sessio, ID_GRUP, data),
    )


def _afegeix_versio(conn: sqlite3.Connection, id_versio: int, nom: str, informe: str | None = None) -> None:
    conn.execute(
        "INSERT INTO versio_horari (id_versio, nom, informe_json) VALUES (?, ?, ?)",
        (id_versio, nom, informe),
    )


def _afegeix_titulacio(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO titulacio (codi, nom, nivell) VALUES ('GF9', 'Grau Fals 9', 'grau')")


def _afegeix_registre(conn: sqlite3.Connection, de_aula: str | None, a_aula: str | None) -> None:
    conn.execute(
        "INSERT INTO registre_canvi (id_versio_origen, id_versio_desti, id_sessio, de_aula, a_aula, "
        "motiu, afectats, data_avis) VALUES (1, 2, 'S90001', ?, ?, 'Prova', 'docent', '2026-11-07')",
        (de_aula, a_aula),
    )


def _preparar_registre(conn: sqlite3.Connection) -> None:
    _preparar_grup(conn)
    _afegeix_sessio(conn, "S90001", "2027-01-15")
    _afegeix_versio(conn, 1, "v1")
    _afegeix_versio(conn, 2, "v2")
    conn.execute("INSERT INTO aula (codi) VALUES ('Q1/9001')")


@pytest.fixture
def conn_buida(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connexio = connect(tmp_path / "esquema.db")
    yield connexio
    connexio.close()


@pytest.fixture
def conn(conn_buida: sqlite3.Connection) -> sqlite3.Connection:
    pujar(conn_buida, DIR_MIGRACIONS)
    return conn_buida


# --- migració i taules -----------------------------------------------------------------------------------------------


def test_migracio_real_es_0001_esquema_inicial() -> None:
    assert [(m.version, m.nom) for m in descobrir(DIR_MIGRACIONS)] == [(1, "esquema_inicial")]


def test_pujar_retorna_la_0001(conn_buida: sqlite3.Connection) -> None:
    assert pujar(conn_buida, DIR_MIGRACIONS) == [1]


def test_exactament_26_taules_d_usuari_mes_schema_migrations(conn: sqlite3.Connection) -> None:
    assert _taules(conn) == TAULES_ESPERADES


def test_grup_cohort_i_el_seu_index_no_existeixen(conn: sqlite3.Connection) -> None:
    assert "grup_cohort" not in _taules(conn)
    assert "ix_grup_cohort_coh" not in _indexos(conn)


@pytest.mark.parametrize(
    ("index", "taula", "columnes"),
    [
        ("ix_sessio_escenari", "sessio", ["id_escenari"]),
        ("ix_sessio_aules_addicionals", "sessio", ["aules_addicionals_partida"]),
        ("ix_indisp_escenari", "indisponibilitat_profe", ["id_escenari"]),
        ("ix_versio_escenari", "versio_horari", ["id_escenari"]),
        ("ix_registre_desti", "registre_canvi", ["id_versio_desti"]),
    ],
)
def test_index_nou_sobre_la_columna_esperada(
    conn: sqlite3.Connection, index: str, taula: str, columnes: list[str]
) -> None:
    fila = conn.execute("SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?", (index,)).fetchone()
    assert fila is not None
    assert fila[0] == taula
    assert _columnes_index(conn, index) == columnes


# --- grup.torn_requerit ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("torn", ["mati", "tarda"])
def test_grup_accepta_mati_i_tarda(conn: sqlite3.Connection, torn: str) -> None:
    _preparar_grup(conn, torn)
    fila = conn.execute("SELECT torn_requerit FROM grup WHERE id_grup = ?", (ID_GRUP,)).fetchone()
    assert fila[0] == torn


@pytest.mark.parametrize("torn", ["nit", "MATI", ""])
def test_grup_rebutja_valors_fora_del_domini(conn: sqlite3.Connection, torn: str) -> None:
    _base(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _afegeix_grup(conn, torn)


def test_grup_rebutja_torn_null(conn: sqlite3.Connection) -> None:
    _base(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _afegeix_grup(conn, None)


# --- cohort.torn_requerit --------------------------------------------------------------------------------------------


def test_cohort_accepta_torn_null(conn: sqlite3.Connection) -> None:
    _afegeix_titulacio(conn)
    conn.execute("INSERT INTO cohort (id_cohort, titulacio, curs, torn_requerit) VALUES ('GF9:1r', 'GF9', '1r', NULL)")
    fila = conn.execute("SELECT torn_requerit FROM cohort WHERE id_cohort = 'GF9:1r'").fetchone()
    assert fila[0] is None


@pytest.mark.parametrize("torn", ["nit", ""])
def test_cohort_rebutja_torn_fora_del_domini(conn: sqlite3.Connection, torn: str) -> None:
    _afegeix_titulacio(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cohort (id_cohort, titulacio, curs, torn_requerit) VALUES ('GF9:1r', 'GF9', '1r', ?)",
            (torn,),
        )


# --- registre_canvi: FK a aula ---------------------------------------------------------------------------------------


def test_registre_de_aula_inexistent_falla(conn: sqlite3.Connection) -> None:
    _preparar_registre(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _afegeix_registre(conn, "NO/0000", None)


def test_registre_a_aula_inexistent_falla(conn: sqlite3.Connection) -> None:
    _preparar_registre(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _afegeix_registre(conn, None, "NO/0000")


def test_registre_aules_null_s_accepten(conn: sqlite3.Connection) -> None:
    _preparar_registre(conn)
    _afegeix_registre(conn, None, None)
    assert conn.execute("SELECT COUNT(*) FROM registre_canvi").fetchone()[0] == 1


def test_registre_aula_existent_s_accepta(conn: sqlite3.Connection) -> None:
    _preparar_registre(conn)
    _afegeix_registre(conn, "Q1/9001", "Q1/9001")
    assert conn.execute("SELECT COUNT(*) FROM registre_canvi").fetchone()[0] == 1


# --- versio_horari.informe_json --------------------------------------------------------------------------------------


def test_informe_json_accepta_json_valid(conn: sqlite3.Connection) -> None:
    _afegeix_versio(conn, 1, "v1", '{"a": 1}')
    fila = conn.execute("SELECT informe_json FROM versio_horari WHERE id_versio = 1").fetchone()
    assert fila[0] == '{"a": 1}'


def test_informe_json_null_s_accepta(conn: sqlite3.Connection) -> None:
    _afegeix_versio(conn, 1, "v1", None)
    fila = conn.execute("SELECT informe_json FROM versio_horari WHERE id_versio = 1").fetchone()
    assert fila[0] is None


@pytest.mark.parametrize("informe", ["no es json", "{'a': 1}", '{"a": '])
def test_informe_json_rebutja_json_invalid(conn: sqlite3.Connection, informe: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _afegeix_versio(conn, 1, "v1", informe)


# --- sessio.semestre -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "semestre"),
    [
        ("2027-01-15", 1),
        ("2027-02-15", 2),
        ("2026-09-15", 1),
        ("2026-08-31", 2),
        ("2026-09-01", 1),
        ("2027-01-31", 1),
        ("2027-02-01", 2),
    ],
)
def test_semestre_es_calcula_per_data(conn: sqlite3.Connection, data: str, semestre: int) -> None:
    _preparar_grup(conn)
    _afegeix_sessio(conn, "S90001", data)
    fila = conn.execute("SELECT semestre FROM sessio WHERE id_sessio = 'S90001'").fetchone()
    assert fila[0] == semestre


# --- claus foranes ---------------------------------------------------------------------------------------------------


def test_foreign_key_check_buit_amb_dades_de_prova(conn: sqlite3.Connection) -> None:
    _preparar_registre(conn)
    _afegeix_titulacio(conn)
    conn.execute(
        "INSERT INTO cohort (id_cohort, titulacio, curs, torn_requerit) VALUES ('GF9:1r', 'GF9', '1r', 'mati')"
    )
    conn.execute("INSERT INTO assignatura_cohort (codi, id_cohort) VALUES ('900001', 'GF9:1r')")
    conn.execute("INSERT INTO profe (id_profe) VALUES ('D901')")
    conn.execute("INSERT INTO docencia (id_profe, id_grup, vigent_des_de) VALUES ('D901', ?, '2026-09-01')", (ID_GRUP,))
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


# --- baixar i tornar a pujar -----------------------------------------------------------------------------------------


def test_baixar_1_deixa_nomes_schema_migrations(conn: sqlite3.Connection) -> None:
    assert baixar(conn, 1, DIR_MIGRACIONS) == [1]
    assert _taules(conn) == ["schema_migrations"]


def test_pujar_de_nou_despres_de_baixar(conn: sqlite3.Connection) -> None:
    baixar(conn, 1, DIR_MIGRACIONS)
    assert pujar(conn, DIR_MIGRACIONS) == [1]
    assert _taules(conn) == TAULES_ESPERADES


# --- contracte del fitxer up -----------------------------------------------------------------------------------------


def test_up_no_conte_pragma_ni_transaccions_propies() -> None:
    texte = (DIR_MIGRACIONS / "0001_esquema_inicial.up.sql").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(PRAGMA|BEGIN|COMMIT)\b", texte, re.IGNORECASE | re.MULTILINE)
