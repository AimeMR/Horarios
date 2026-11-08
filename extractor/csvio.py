"""Lectura de los CSV del paquete con validación de cabecera y de número de campos por fila.

Los errores indican fichero, línea y columna; nunca el contenido de una celda.
"""

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from extractor.errors import CargaError

_LINIA_CABECERA = 1


@dataclass(frozen=True)
class FilaCsv:
    linia: int
    valors: Mapping[str, str]


def llegir_csv(path: Path, columnes: Iterable[str]) -> list[FilaCsv]:
    """Lee `path` y devuelve sus filas; falla si falta alguna de `columnes` o una fila no cuadra con la cabecera.

    `linia` es la línea física donde acaba el registro (cabecera = 1), según `csv.reader.line_num`.
    """
    try:
        with path.open(encoding="utf-8-sig", newline="") as fitxer:
            lector = csv.DictReader(fitxer)
            _comprovar_cabecera(path.name, lector.fieldnames, columnes)
            return [_fila(path.name, lector.line_num, fila) for fila in lector]
    except FileNotFoundError as error:
        raise CargaError(path.name, None, None, "el fichero no existe") from error
    except UnicodeDecodeError as error:
        raise CargaError(path.name, None, None, "el fichero no está en UTF-8") from error
    except csv.Error as error:
        raise CargaError(path.name, None, None, "el fichero no es un CSV válido") from error
    except OSError as error:
        raise CargaError(path.name, None, None, "no se puede leer el fichero") from error


def _comprovar_cabecera(fichero: str, cabecera: Iterable[str] | None, columnes: Iterable[str]) -> None:
    presents = set(cabecera or ())
    for columna in columnes:
        if columna not in presents:
            raise CargaError(fichero, _LINIA_CABECERA, columna, f"falta la columna {columna} en la cabecera")


def _fila(fichero: str, linia: int, fila: Mapping[str | None, str | None]) -> FilaCsv:
    """DictReader pone los campos sobrantes bajo la clave `None` y rellena los que faltan con `None`."""
    valors: dict[str, str] = {}
    for columna, valor in fila.items():
        if columna is None:
            raise CargaError(fichero, linia, None, "la fila tiene más campos que la cabecera")
        if valor is None:
            raise CargaError(fichero, linia, None, "la fila tiene menos campos que la cabecera")
        valors[columna] = valor
    return FilaCsv(linia=linia, valors=valors)
