"""Utilidades compartidas por los cargadores: lectura de JSON, `id_grup`, conjuntos de códigos y escenarios.

`llegir_escenaris` es la ÚNICA fuente de los escenarios del paquete y de su fichero de sesiones extra: la usan
`carregar_catalegs` (titulaciones, cohortes y plan `NOU`) y `carregar_escenaris` (carga de las sesiones), de modo que
los dos ven exactamente los mismos ficheros. Un `sessions_extra.csv` de una carpeta cuyo `escenari.json` no lo declara
en la clave `sessions_extra` se ignora.
"""

import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from extractor.errors import CargaError

PATRO_ESCENARI: str = "escenaris/*/escenari.json"
SEPARADOR_ID_GRUP: str = "·"
PATRO_FITXER_CSV: re.Pattern[str] = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}\.csv")
CLAU_SESSIONS_EXTRA: str = "sessions_extra"


@dataclass(frozen=True)
class EscenariJson:
    """Un `escenaris/<dir>/escenari.json` leído y con su fichero de sesiones extra validado."""

    id_escenari: str
    fichero: str
    dades: Mapping[str, object]
    sessions_extra: str | None


def llegir_json(path: Path, fichero: str) -> Mapping[str, object]:
    """Objeto JSON del fichero; cualquier problema es `CargaError(fichero, None, None, motiu)` sin el contenido."""
    try:
        dades: object = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise CargaError(fichero, None, None, "el fichero no está en UTF-8") from error
    except json.JSONDecodeError as error:
        raise CargaError(fichero, None, None, "el fichero no es un JSON válido") from error
    except RecursionError as error:
        raise CargaError(fichero, None, None, "el JSON está demasiado anidado") from error
    except OSError as error:
        raise CargaError(fichero, None, None, "no se puede leer el fichero") from error
    if not isinstance(dades, dict):
        raise CargaError(fichero, None, None, "el JSON no es un objeto")
    return dades


def id_grup(codi: str, grup: str) -> str:
    """Identificador de grupo: `codi + "·" + grup` (U+00B7)."""
    return f"{codi}{SEPARADOR_ID_GRUP}{grup}"


def codis(conn: sqlite3.Connection, sql: str) -> frozenset[str]:
    """Primera columna de una consulta fija (sin parámetros) como conjunto de textos."""
    return frozenset(str(fila[0]) for fila in conn.execute(sql))


def llegir_escenaris(paquet: Path) -> tuple[EscenariJson, ...]:
    """Cada `escenaris/<dir>/escenari.json`, en orden alfabético de `<dir>`, leído y validado con las mismas reglas
    para todos los cargadores que lo llaman."""
    fitxers = sorted(paquet.glob(PATRO_ESCENARI), key=lambda path: path.parent.name)
    return tuple(_llegir_escenari(paquet, path) for path in fitxers)


def _llegir_escenari(paquet: Path, path: Path) -> EscenariJson:
    fichero = path.relative_to(paquet).as_posix()
    dades = llegir_json(path, fichero)
    id_escenari = path.parent.name
    return EscenariJson(
        id_escenari=id_escenari,
        fichero=fichero,
        dades=dades,
        sessions_extra=_sessions_extra(dades, fichero, id_escenari),
    )


def _sessions_extra(dades: Mapping[str, object], fichero: str, id_escenari: str) -> str | None:
    """Ruta relativa al paquete del CSV que nombra `sessions_extra`; solo un nombre de la carpeta, nunca una ruta."""
    valor = dades.get(CLAU_SESSIONS_EXTRA)
    if valor is None:
        return None
    if not isinstance(valor, str) or not PATRO_FITXER_CSV.fullmatch(valor):
        raise CargaError(
            fichero, None, CLAU_SESSIONS_EXTRA, "se esperaba el nombre de un fichero CSV de la carpeta del escenario"
        )
    return f"escenaris/{id_escenari}/{valor}"
