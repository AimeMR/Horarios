"""Fixtures y utilidades compartidas por los tests de carga.

Todo el contenido de `fixtures/paquet_fals` es inventado. Los tests nunca leen el paquete real.
"""

import csv
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import connect
from extractor.errors import CargaError
from extractor.migrate import pujar

PAQUET_FALS = Path(__file__).resolve().parent / "fixtures" / "paquet_fals"

Fila = tuple[object, ...]


@pytest.fixture
def paquet_fals() -> Path:
    """Ruta al paquete falso. Solo lectura: los tests que modifican celdas usan `copia_paquet`."""
    return PAQUET_FALS


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """BD temporal en `tmp_path`, abierta con `connect` y migrada con `pujar`; se cierra al terminar."""
    connexio = connect(tmp_path / "horaris.db")
    try:
        pujar(connexio)
        yield connexio
    finally:
        connexio.close()


@pytest.fixture
def copia_paquet(tmp_path: Path, paquet_fals: Path) -> Path:
    """Copia del paquete falso en `tmp_path/paquet`, para casos inválidos que modifican una celda."""
    desti = tmp_path / "paquet"
    shutil.copytree(paquet_fals, desti)
    return desti


def canviar_cella(fitxer: Path, columna: str, fila: int, valor: str) -> None:
    """Sustituye una celda de un CSV por nombre de columna.

    `fila` es el número de fila de datos: 1 = primera fila tras la cabecera (línea 2 del fichero).
    """
    with fitxer.open(encoding="utf-8-sig", newline="") as lectura:
        files = list(csv.reader(lectura))
    files[fila][files[0].index(columna)] = valor
    with fitxer.open("w", encoding="utf-8", newline="") as escriptura:
        csv.writer(escriptura, lineterminator="\n").writerows(files)


def consulta(conn: sqlite3.Connection, sql: str, parametres: tuple[str, ...] = ()) -> list[Fila]:
    """Filas de una consulta SELECT parametrizada, como tuplas."""
    return [tuple(fila) for fila in conn.execute(sql, parametres).fetchall()]


def comptar(conn: sqlite3.Connection, sql: str, parametres: tuple[str, ...] = ()) -> int:
    """Valor entero de una consulta SELECT COUNT(*)."""
    valor = consulta(conn, sql, parametres)[0][0]
    assert isinstance(valor, int)
    return valor


def afirma_error_carrega(error: CargaError, fichero: str, linia: int | None, columna: str | None, valor: str) -> None:
    """Comprueba fichero, línea y columna del error, y que el mensaje no repite el valor de la celda."""
    assert error.fichero == fichero
    assert error.linia == linia
    assert error.columna == columna
    assert valor not in str(error)
