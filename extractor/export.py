"""Exporta una versión de horario guardada en SQLite al CSV de entrega `id_sessio,dia,h_ini,aula[,data]`.

El fichero sale en UTF-8 sin BOM, con LF y salto final, ordenado por `id_sessio`; NULL se escribe como campo vacío.
"""

import csv
import re
import sqlite3
from pathlib import Path

from extractor.errors import ExportError

PATRO_NOM_VERSIO: re.Pattern[str] = re.compile(r"[A-Za-z0-9._-]{1,64}")

_CAPCALERA: tuple[str, ...] = ("id_sessio", "dia", "h_ini", "aula")
_COLUMNA_DATA = "data"
_POSICIO_DATA = len(_CAPCALERA)

_EXISTEIX_VERSIO = "SELECT 1 FROM versio_horari WHERE nom = ?"
_ASSIGNACIONS = (
    "SELECT a.id_sessio, a.dia, a.h_ini, a.aula, a.data FROM assignacio a JOIN versio_horari v USING (id_versio) "
    "WHERE v.nom = ? ORDER BY a.id_sessio"
)


def validar_nom_versio(versio: str) -> str:
    """Devuelve el nombre si casa entero con `PATRO_NOM_VERSIO`; si no, `ExportError` (sin repetir el valor)."""
    if PATRO_NOM_VERSIO.fullmatch(versio) is None:
        raise ExportError("nombre de versión no válido: solo letras ASCII, dígitos, '.', '_' o '-' (1 a 64)")
    return versio


def exportar(conn: sqlite3.Connection, versio: str, desti: Path) -> int:
    """Escribe la versión `versio` en `desti` (crea la carpeta padre) y devuelve el número de filas escritas."""
    validar_nom_versio(versio)
    if conn.execute(_EXISTEIX_VERSIO, (versio,)).fetchone() is None:
        raise ExportError("la versión de horario no existe")
    files = [_fila_text(fila) for fila in conn.execute(_ASSIGNACIONS, (versio,))]
    amb_data = any(fila[_POSICIO_DATA] for fila in files)
    _escriu_csv(desti, files, amb_data)
    return len(files)


def _fila_text(fila: sqlite3.Row | tuple[object, ...]) -> tuple[str, ...]:
    return tuple(_text(fila[posicio]) for posicio in range(_POSICIO_DATA + 1))


def _text(valor: object) -> str:
    return "" if valor is None else str(valor)


def _escriu_csv(desti: Path, files: list[tuple[str, ...]], amb_data: bool) -> None:
    capcalera = (*_CAPCALERA, _COLUMNA_DATA) if amb_data else _CAPCALERA
    amplada = len(capcalera)
    try:
        desti.parent.mkdir(parents=True, exist_ok=True)
        with open(desti, "w", encoding="utf-8", newline="") as fitxer:
            escriptor = csv.writer(fitxer, lineterminator="\n")
            escriptor.writerow(capcalera)
            escriptor.writerows(fila[:amplada] for fila in files)
    except OSError as exc:
        raise ExportError("no se ha podido escribir el CSV exportado") from exc
