import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import _comprova_foreign_keys, connect
from extractor.errors import ExtractorError


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connexio = connect(tmp_path / "prova.db")
    yield connexio
    connexio.close()


def test_foreign_keys_activades(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fk_violada_falla(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE pare (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE fill (id INTEGER PRIMARY KEY, id_pare INTEGER NOT NULL REFERENCES pare(id))")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO fill (id, id_pare) VALUES (?, ?)", (1, 99))


def test_row_factory_es_row(conn: sqlite3.Connection) -> None:
    fila = conn.execute("SELECT 1 AS u").fetchone()
    assert isinstance(fila, sqlite3.Row)
    assert fila["u"] == 1


def test_busy_timeout(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_autocommit_sense_transaccio_implicita(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t (id) VALUES (?)", (1,))
    assert conn.isolation_level is None
    assert not conn.in_transaction


def test_comprovacio_falla_si_foreign_keys_desactivades(tmp_path: Path) -> None:
    crua = sqlite3.connect(tmp_path / "crua.db")
    try:
        crua.execute("PRAGMA foreign_keys = OFF")
        with pytest.raises(ExtractorError):
            _comprova_foreign_keys(crua)
    finally:
        crua.close()
