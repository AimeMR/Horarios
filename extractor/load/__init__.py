"""Cargadores del paquete de datos en la BD (catálogos, sesiones, escenarios y versión de partida).

`carregar` orquesta la carga completa en UNA transacción: o se carga todo el paquete o no queda nada.
"""

import sqlite3
from pathlib import Path

from extractor.errors import ExtractorError
from extractor.load.catalegs import carregar_catalegs
from extractor.load.escenaris import carregar_escenaris
from extractor.load.partida import carregar_partida
from extractor.load.sessions import carregar_sessions

# Todas las tablas del esquema salvo schema_migrations, hijas antes que padres (orden válido para DELETE con FKs).
TAULES_DADES: tuple[str, ...] = (
    "registre_canvi",
    "relaxacio_sessio",
    "relaxacio",
    "assignacio",
    "versio_horari",
    "canvi_alumnes",
    "cancellacio",
    "tancament_aula",
    "calendari",
    "sessio",
    "activitat",
    "indisponibilitat_profe",
    "escenari",
    "docencia",
    "profe",
    "grup",
    "assignatura_pla",
    "assignatura_cohort",
    "assignatura",
    "cohort",
    "pla_titulacio",
    "pla_estudis",
    "titulacio",
    "aula",
    "departament",
    "facultat",
)

FITXER_SESSIONS = "sessions.csv"
FITXER_ACTIVITATS = "activitats.csv"


def esta_migrada(conn: sqlite3.Connection) -> bool:
    """Cierto si existe la tabla `sessio` (la migración inicial está aplicada)."""
    fila = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sessio'").fetchone()
    return fila is not None


def esta_carregada(conn: sqlite3.Connection) -> bool:
    """Cierto si `sessio` tiene alguna fila."""
    return conn.execute("SELECT 1 FROM sessio LIMIT 1").fetchone() is not None


def buidar(conn: sqlite3.Connection) -> None:
    """Borra las filas de todas las tablas de datos, sin tocar el esquema. No abre ni cierra transacciones."""
    for taula in TAULES_DADES:
        # El nombre de la tabla sale de la constante TAULES_DADES del módulo, nunca de entrada externa.
        conn.execute(f"DELETE FROM {taula}")  # noqa: S608  # nosec B608


def carregar(conn: sqlite3.Connection, paquet: Path, reset: bool = False) -> dict[str, int]:
    """Carga el paquete completo en una sola transacción y devuelve el número de filas de cada tabla de datos.

    Sin migrar, o ya cargada y sin `reset`, lanza `ExtractorError` sin tocar nada. Ante cualquier error hace
    ROLLBACK y relanza la excepción: la BD queda como estaba.
    """
    if not esta_migrada(conn):
        raise ExtractorError("la BD no está migrada: ejecuta migrate")
    if not reset and esta_carregada(conn):
        raise ExtractorError("la BD ya está cargada: usa --reset")
    conn.execute("BEGIN")
    try:
        _carregar_tot(conn, paquet, reset)
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return _recomptes(conn)


def _carregar_tot(conn: sqlite3.Connection, paquet: Path, reset: bool) -> None:
    if reset:
        buidar(conn)
    carregar_catalegs(conn, paquet)
    carregar_sessions(conn, paquet, FITXER_SESSIONS, FITXER_ACTIVITATS, None)
    carregar_escenaris(conn, paquet)
    carregar_partida(conn, paquet)
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ExtractorError("la carga deja referencias rotas entre tablas (foreign_key_check)")


def _recomptes(conn: sqlite3.Connection) -> dict[str, int]:
    recomptes: dict[str, int] = {}
    for taula in TAULES_DADES:
        # El nombre de la tabla sale de la constante TAULES_DADES del módulo, nunca de entrada externa.
        fila = conn.execute(f"SELECT COUNT(*) FROM {taula}").fetchone()  # noqa: S608  # nosec B608
        recomptes[taula] = int(fila[0])
    return recomptes
