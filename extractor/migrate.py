"""Runner de migraciones SQL versionadas (db/migrations/NNNN_nombre.up.sql / .down.sql).

Cada migración se aplica o revierte en su propia transacción y queda registrada en `schema_migrations` con el
sha256 de su `up`. La conexión tiene que venir de `extractor.db.connect` (autocommit, `isolation_level=None`).
"""

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from extractor.errors import MigracioError

DIR_MIGRACIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"

_NOM_VALID = re.compile(r"([0-9]{4})_([a-z0-9_]+)\.(up|down)\.sql")

_CREA_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    nom         TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    aplicada_el TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migracio:
    version: int
    nom: str
    up: Path
    down: Path


@dataclass(frozen=True)
class _Script:
    fitxer: Path
    sql: str
    sha256: str


def descobrir(directori: Path = DIR_MIGRACIONS) -> list[Migracio]:
    """Devuelve las migraciones del directorio ordenadas por versión, comprobando que formen una serie 1..N."""
    fitxers = _fitxers_per_versio(directori)
    migracions = [_migracio(version, parells) for version, parells in sorted(fitxers.items())]
    _comprova_serie(migracions, directori)
    return migracions


def versions_aplicades(conn: sqlite3.Connection) -> list[int]:
    """Versiones registradas en `schema_migrations`, en orden; `[]` si la tabla aún no existe."""
    return sorted(_aplicades(conn))


def pujar(conn: sqlite3.Connection, directori: Path = DIR_MIGRACIONS) -> list[int]:
    """Aplica las migraciones pendientes en orden y devuelve sus versiones."""
    _comprova_sense_transaccio(conn)
    migracions = descobrir(directori)
    conn.execute(_CREA_SCHEMA_MIGRATIONS)
    aplicades = _aplicades(conn)
    _comprova_integritat(migracions, aplicades, directori)
    pendents = [m for m in migracions if m.version not in aplicades]
    for migracio in pendents:
        _aplica(conn, migracio)
    conn.execute("PRAGMA journal_mode = WAL")
    return [m.version for m in pendents]


def baixar(conn: sqlite3.Connection, n: int, directori: Path = DIR_MIGRACIONS) -> list[int]:
    """Revierte las `n` migraciones aplicadas más recientes, de la más nueva a la más vieja."""
    _comprova_sense_transaccio(conn)
    aplicades = versions_aplicades(conn)
    if n < 1 or n > len(aplicades):
        raise MigracioError(f"no se pueden revertir {n} migraciones: hay {len(aplicades)} aplicadas")
    per_versio = {m.version: m for m in descobrir(directori)}
    a_revertir = list(reversed(aplicades))[:n]
    absents = [version for version in a_revertir if version not in per_versio]
    if absents:
        raise MigracioError(f"migraciones aplicadas que ya no están en {directori.name}: {absents}")
    for version in a_revertir:
        _reverteix(conn, per_versio[version])
    return a_revertir


def _fitxers_per_versio(directori: Path) -> dict[int, dict[str, Path]]:
    if not directori.is_dir():
        raise MigracioError(f"{directori.name}: el directorio de migraciones no existe")
    fitxers: dict[int, dict[str, Path]] = {}
    noms: dict[int, str] = {}
    for fitxer in sorted(directori.iterdir()):
        if not fitxer.is_file() or not fitxer.name.lower().endswith(".sql"):
            continue
        version, nom, sentit = _parseja_nom(fitxer)
        if noms.setdefault(version, nom) != nom:
            raise MigracioError(f"{fitxer.name}: la versión {version} ya existe con el nombre {noms[version]}")
        fitxers.setdefault(version, {})[sentit] = fitxer
    return fitxers


def _parseja_nom(fitxer: Path) -> tuple[int, str, str]:
    coincidencia = _NOM_VALID.fullmatch(fitxer.name)
    if coincidencia is None:
        raise MigracioError(f"{fitxer.name}: nombre de migración inválido (se espera NNNN_nombre.up|down.sql)")
    return int(coincidencia.group(1)), coincidencia.group(2), coincidencia.group(3)


def _migracio(version: int, parells: dict[str, Path]) -> Migracio:
    for sentit in ("up", "down"):
        if sentit not in parells:
            existent = next(iter(parells.values()))
            raise MigracioError(f"{existent.name}: falta el fichero {sentit} de la versión {version}")
    nom = _parseja_nom(parells["up"])[1]
    return Migracio(version=version, nom=nom, up=parells["up"], down=parells["down"])


def _comprova_serie(migracions: list[Migracio], directori: Path) -> None:
    for esperada, migracio in enumerate(migracions, start=1):
        if migracio.version != esperada:
            raise MigracioError(
                f"{migracio.up.name}: las versiones de {directori.name} tienen que ir de 1 en 1 desde 1 "
                f"(se esperaba la {esperada})"
            )


def _aplicades(conn: sqlite3.Connection) -> dict[int, str]:
    existeix = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if existeix is None:
        return {}
    files = conn.execute("SELECT version, sha256 FROM schema_migrations").fetchall()
    return {int(fila[0]): str(fila[1]) for fila in files}


def _comprova_integritat(migracions: list[Migracio], aplicades: dict[int, str], directori: Path) -> None:
    per_versio = {m.version: m for m in migracions}
    absents = sorted(version for version in aplicades if version not in per_versio)
    if absents:
        raise MigracioError(f"migraciones aplicadas que ya no están en {directori.name}: {absents}")
    for version, sha256 in aplicades.items():
        fitxer = per_versio[version].up
        if _llegeix(fitxer).sha256 != sha256:
            raise MigracioError(f"{fitxer.name}: el fichero ha cambiado después de aplicarse")


def _llegeix(fitxer: Path) -> _Script:
    try:
        contingut = fitxer.read_bytes()
        sql = contingut.decode("utf-8")
    except OSError as exc:
        raise MigracioError(f"{fitxer.name}: no se puede leer el fichero") from exc
    except UnicodeDecodeError as exc:
        raise MigracioError(f"{fitxer.name}: el fichero no está en UTF-8") from exc
    return _Script(fitxer=fitxer, sql=sql, sha256=hashlib.sha256(contingut).hexdigest())


def _aplica(conn: sqlite3.Connection, migracio: Migracio) -> None:
    script = _llegeix(migracio.up)
    _executa_en_transaccio(
        conn,
        script,
        "INSERT INTO schema_migrations (version, nom, sha256, aplicada_el) VALUES (?, ?, ?, ?)",
        (migracio.version, migracio.nom, script.sha256, datetime.now(UTC).isoformat(timespec="seconds")),
    )


def _reverteix(conn: sqlite3.Connection, migracio: Migracio) -> None:
    _executa_en_transaccio(
        conn,
        _llegeix(migracio.down),
        "DELETE FROM schema_migrations WHERE version = ?",
        (migracio.version,),
    )


def _executa_en_transaccio(
    conn: sqlite3.Connection, script: _Script, registre: str, parametres: tuple[int | str, ...]
) -> None:
    """Ejecuta el script y la sentencia de registro en una sola transacción; ROLLBACK si algo falla.

    `executescript` hace COMMIT de una transacción pendiente antes de empezar, así que el `BEGIN` va dentro del
    propio script y la transacción sigue abierta al acabar: el registro parametrizado y el COMMIT van después.
    """
    try:
        conn.executescript("BEGIN;\n" + script.sql + "\n;")
        if not conn.in_transaction:
            raise MigracioError(f"{script.fitxer.name}: la migración no puede cerrar la transacción (BEGIN/COMMIT)")
        conn.execute(registre, parametres)
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        _desfes(conn)
        raise MigracioError(f"{script.fitxer.name}: la migración ha fallado y se ha revertido") from exc
    except BaseException:
        _desfes(conn)
        raise


def _desfes(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        conn.execute("ROLLBACK")


def _comprova_sense_transaccio(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        raise MigracioError("no se pueden aplicar migraciones con una transacción abierta")
