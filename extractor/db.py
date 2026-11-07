"""Conexión a SQLite. Es el único sitio donde se abren conexiones."""

import sqlite3
from pathlib import Path

from extractor.errors import ExtractorError


def connect(path: Path) -> sqlite3.Connection:
    """Abre la BD en modo autocommit (las transacciones se abren con BEGIN explícito).

    Activa y comprueba las claves foráneas, fija busy_timeout y devuelve filas `sqlite3.Row`.
    """
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        _comprova_foreign_keys(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def _comprova_foreign_keys(conn: sqlite3.Connection) -> None:
    fila = conn.execute("PRAGMA foreign_keys").fetchone()
    if fila is None or fila[0] != 1:
        raise ExtractorError("no se han podido activar las claves foráneas de SQLite")
