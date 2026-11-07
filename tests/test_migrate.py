"""Tests del runner de migraciones (extractor/migrate.py) con migraciones falsas.

Las migraciones válidas están en tests/fixtures/migrations/valides (0001_crear_a, 0002_crear_b, 0003_index_b).
Cada test trabaja sobre una copia en tmp_path; los casos inválidos se generan ahí mismo.
"""

import hashlib
import re
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import connect
from extractor.errors import MigracioError
from extractor.migrate import DIR_MIGRACIONS, Migracio, baixar, descobrir, pujar, versions_aplicades

FIXTURES_VALIDES = Path(__file__).resolve().parent / "fixtures" / "migrations" / "valides"


def _escriu(directori: Path, nom: str, contingut: str) -> None:
    (directori / nom).write_text(contingut, encoding="utf-8", newline="\n")


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


def _schema_migrations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT version, nom, sha256, aplicada_el FROM schema_migrations ORDER BY version").fetchall()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connexio = connect(tmp_path / "prova.db")
    yield connexio
    connexio.close()


@pytest.fixture
def migracions(tmp_path: Path) -> Path:
    """Copia de las migraciones falsas válidas; cada test puede alterar su copia."""
    destí = tmp_path / "migracions"
    shutil.copytree(FIXTURES_VALIDES, destí)
    return destí


@pytest.fixture
def pujades(conn: sqlite3.Connection, migracions: Path) -> sqlite3.Connection:
    pujar(conn, migracions)
    return conn


def _pujar_migracio_trencada(conn: sqlite3.Connection, migracions: Path) -> MigracioError:
    """0001 válida; 0002 con un CREATE correcto seguido de SQL roto. No queda 0003."""
    for nom in ("0002_crear_b.up.sql", "0002_crear_b.down.sql", "0003_index_b.up.sql", "0003_index_b.down.sql"):
        (migracions / nom).unlink()
    _escriu(
        migracions,
        "0002_trencada.up.sql",
        "CREATE TABLE taula_parcial_7731 (id INTEGER PRIMARY KEY);\nCREATE TABLA trencada_7731 (x);\n",
    )
    _escriu(migracions, "0002_trencada.down.sql", "DROP TABLE taula_parcial_7731;\n")
    with pytest.raises(MigracioError) as info:
        pujar(conn, migracions)
    return info.value


# --- descobrir -------------------------------------------------------------------------------------------------------


def test_descobrir_ordena_per_versio(migracions: Path) -> None:
    assert [m.version for m in descobrir(migracions)] == [1, 2, 3]


def test_descobrir_retorna_noms_i_fitxers(migracions: Path) -> None:
    trobades = descobrir(migracions)
    assert all(isinstance(m, Migracio) for m in trobades)
    assert [(m.version, m.nom, m.up.name, m.down.name) for m in trobades] == [
        (1, "crear_a", "0001_crear_a.up.sql", "0001_crear_a.down.sql"),
        (2, "crear_b", "0002_crear_b.up.sql", "0002_crear_b.down.sql"),
        (3, "index_b", "0003_index_b.up.sql", "0003_index_b.down.sql"),
    ]


def test_descobrir_una_sola_migracio_valida(migracions: Path) -> None:
    for nom in ("0002_crear_b.up.sql", "0002_crear_b.down.sql", "0003_index_b.up.sql", "0003_index_b.down.sql"):
        (migracions / nom).unlink()
    assert [m.version for m in descobrir(migracions)] == [1]


@pytest.mark.parametrize("fitxer", ["notes.txt", "0004_x.up.sql.bak", "0004_x.sql.orig", "README.md"])
def test_descobrir_ignora_fitxers_que_no_acaben_en_sql(migracions: Path, fitxer: str) -> None:
    _escriu(migracions, fitxer, "-- no es una migració\n")
    assert [m.version for m in descobrir(migracions)] == [1, 2, 3]


@pytest.mark.parametrize(
    "fitxer",
    [
        "0001_Crear.up.sql",
        "001_crear.up.sql",
        "0001-crear.up.sql",
        "0001_crear.sql",
        "0001_crear.mig.sql",
        "0001_crear b.up.sql",
        "0001_crear.UP.sql",
    ],
)
def test_descobrir_nom_sql_invalid_falla_i_nomena_el_fitxer(migracions: Path, fitxer: str) -> None:
    _escriu(migracions, fitxer, "SELECT 1;\n")
    with pytest.raises(MigracioError) as info:
        descobrir(migracions)
    assert fitxer in str(info.value)


def test_descobrir_falta_down_falla(migracions: Path) -> None:
    (migracions / "0002_crear_b.down.sql").unlink()
    with pytest.raises(MigracioError):
        descobrir(migracions)


def test_descobrir_falta_up_falla(migracions: Path) -> None:
    (migracions / "0002_crear_b.up.sql").unlink()
    with pytest.raises(MigracioError):
        descobrir(migracions)


def test_descobrir_versio_repetida_amb_nom_diferent_falla(migracions: Path) -> None:
    _escriu(migracions, "0002_altre.up.sql", "SELECT 1;\n")
    _escriu(migracions, "0002_altre.down.sql", "SELECT 1;\n")
    with pytest.raises(MigracioError):
        descobrir(migracions)


def test_descobrir_no_comenca_en_1_falla(migracions: Path) -> None:
    (migracions / "0001_crear_a.up.sql").unlink()
    (migracions / "0001_crear_a.down.sql").unlink()
    with pytest.raises(MigracioError):
        descobrir(migracions)


def test_descobrir_hueco_entre_versions_falla(migracions: Path) -> None:
    (migracions / "0002_crear_b.up.sql").unlink()
    (migracions / "0002_crear_b.down.sql").unlink()
    with pytest.raises(MigracioError):
        descobrir(migracions)


def test_dir_migracions_es_db_migrations() -> None:
    esperat = Path(__file__).resolve().parent.parent / "db" / "migrations"
    assert DIR_MIGRACIONS.resolve() == esperat


# --- versions_aplicades ----------------------------------------------------------------------------------------------


def test_versions_aplicades_bd_buida_retorna_llista_buida(conn: sqlite3.Connection) -> None:
    assert versions_aplicades(conn) == []


def test_versions_aplicades_despres_de_pujar(pujades: sqlite3.Connection) -> None:
    assert versions_aplicades(pujades) == [1, 2, 3]


# --- pujar -----------------------------------------------------------------------------------------------------------


def test_pujar_aplica_totes_en_ordre_i_retorna_versions(conn: sqlite3.Connection, migracions: Path) -> None:
    assert pujar(conn, migracions) == [1, 2, 3]
    assert _taules(conn) == ["a", "b", "schema_migrations"]
    assert _indexos(conn) == ["ix_b_a"]


def test_segona_pujada_no_aplica_res(pujades: sqlite3.Connection, migracions: Path) -> None:
    assert pujar(pujades, migracions) == []


def test_schema_migrations_guarda_nom_sha_i_data(pujades: sqlite3.Connection) -> None:
    files = _schema_migrations(pujades)
    assert [fila["version"] for fila in files] == [1, 2, 3]
    assert [fila["nom"] for fila in files] == ["crear_a", "crear_b", "index_b"]
    assert all(re.fullmatch(r"[0-9a-fA-F]{64}", fila["sha256"]) for fila in files)
    assert all(fila["aplicada_el"] for fila in files)


def test_sha256_es_el_hash_del_contingut_del_up(pujades: sqlite3.Connection, migracions: Path) -> None:
    files = {fila["version"]: fila["sha256"] for fila in _schema_migrations(pujades)}
    esperat = hashlib.sha256((migracions / "0001_crear_a.up.sql").read_bytes()).hexdigest()
    assert files[1] == esperat


def test_pujar_deixa_journal_mode_wal(pujades: sqlite3.Connection) -> None:
    assert pujades.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


# --- pujar: atomicidad -----------------------------------------------------------------------------------------------


def test_migracio_rota_no_deixa_la_taula_a_mitges(conn: sqlite3.Connection, migracions: Path) -> None:
    _pujar_migracio_trencada(conn, migracions)
    assert "taula_parcial_7731" not in _taules(conn)


def test_migracio_rota_no_registra_la_versio(conn: sqlite3.Connection, migracions: Path) -> None:
    _pujar_migracio_trencada(conn, migracions)
    assert versions_aplicades(conn) == [1]


def test_migracio_rota_conserva_les_anteriors(conn: sqlite3.Connection, migracions: Path) -> None:
    _pujar_migracio_trencada(conn, migracions)
    assert "a" in _taules(conn)


def test_migracio_rota_no_deixa_transaccio_oberta(conn: sqlite3.Connection, migracions: Path) -> None:
    _pujar_migracio_trencada(conn, migracions)
    assert not conn.in_transaction


def test_error_de_migracio_rota_nomena_el_fitxer(conn: sqlite3.Connection, migracions: Path) -> None:
    error = _pujar_migracio_trencada(conn, migracions)
    assert "0002_trencada" in str(error)


def test_error_de_migracio_rota_no_conte_el_sql(conn: sqlite3.Connection, migracions: Path) -> None:
    error = _pujar_migracio_trencada(conn, migracions)
    assert "taula_parcial_7731" not in str(error)
    assert "trencada_7731" not in str(error)


# --- pujar: integridad -----------------------------------------------------------------------------------------------


def test_up_editat_d_una_migracio_aplicada_falla(pujades: sqlite3.Connection, migracions: Path) -> None:
    _escriu(
        migracions,
        "0001_crear_a.up.sql",
        "CREATE TABLE a (id INTEGER PRIMARY KEY, nom TEXT NOT NULL, extra TEXT);\n",
    )
    with pytest.raises(MigracioError):
        pujar(pujades, migracions)


def test_up_editat_no_aplica_les_pendents(conn: sqlite3.Connection, migracions: Path) -> None:
    (migracions / "0003_index_b.up.sql").unlink()
    (migracions / "0003_index_b.down.sql").unlink()
    assert pujar(conn, migracions) == [1, 2]
    _escriu(migracions, "0003_index_b.up.sql", "CREATE INDEX ix_b_a ON b(id_a);\n")
    _escriu(migracions, "0003_index_b.down.sql", "DROP INDEX ix_b_a;\n")
    _escriu(
        migracions,
        "0001_crear_a.up.sql",
        "CREATE TABLE a (id INTEGER PRIMARY KEY, nom TEXT NOT NULL, extra TEXT);\n",
    )
    with pytest.raises(MigracioError):
        pujar(conn, migracions)
    assert versions_aplicades(conn) == [1, 2]


def test_migracio_aplicada_esborrada_del_directori_falla(pujades: sqlite3.Connection, migracions: Path) -> None:
    (migracions / "0003_index_b.up.sql").unlink()
    (migracions / "0003_index_b.down.sql").unlink()
    with pytest.raises(MigracioError):
        pujar(pujades, migracions)
    assert versions_aplicades(pujades) == [1, 2, 3]


# --- baixar ----------------------------------------------------------------------------------------------------------


def test_baixar_1_reverteix_la_3(pujades: sqlite3.Connection, migracions: Path) -> None:
    assert baixar(pujades, 1, migracions) == [3]
    assert versions_aplicades(pujades) == [1, 2]
    assert _indexos(pujades) == []
    assert "b" in _taules(pujades)


def test_baixar_2_despres_deixa_nomes_schema_migrations(pujades: sqlite3.Connection, migracions: Path) -> None:
    baixar(pujades, 1, migracions)
    assert baixar(pujades, 2, migracions) == [2, 1]
    assert _taules(pujades) == ["schema_migrations"]
    assert versions_aplicades(pujades) == []


def test_baixar_totes_les_aplicades_limit_superior(pujades: sqlite3.Connection, migracions: Path) -> None:
    assert baixar(pujades, 3, migracions) == [3, 2, 1]
    assert _taules(pujades) == ["schema_migrations"]


@pytest.mark.parametrize("n", [0, -1])
def test_baixar_n_menor_que_1_falla(pujades: sqlite3.Connection, migracions: Path, n: int) -> None:
    with pytest.raises(MigracioError):
        baixar(pujades, n, migracions)
    assert versions_aplicades(pujades) == [1, 2, 3]


def test_baixar_mes_de_les_aplicades_falla(pujades: sqlite3.Connection, migracions: Path) -> None:
    with pytest.raises(MigracioError):
        baixar(pujades, 4, migracions)
    assert versions_aplicades(pujades) == [1, 2, 3]


def test_pujar_de_nou_despres_de_baixar(pujades: sqlite3.Connection, migracions: Path) -> None:
    baixar(pujades, 3, migracions)
    assert pujar(pujades, migracions) == [1, 2, 3]
    assert _indexos(pujades) == ["ix_b_a"]


def test_baixar_amb_down_rota_no_deixa_res_a_mitges(pujades: sqlite3.Connection, migracions: Path) -> None:
    _escriu(migracions, "0003_index_b.down.sql", "DROP INDEX ix_b_a;\nDROP TABLA rota_8812;\n")
    with pytest.raises(MigracioError):
        baixar(pujades, 1, migracions)
    assert versions_aplicades(pujades) == [1, 2, 3]
    assert "ix_b_a" in _indexos(pujades)
