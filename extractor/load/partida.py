"""Carga de la versión de partida: `versio_horari('partida')` y una `assignacio` por fila de `proposta_partida.csv`.

- `aula` vacía → NULL; `data` → NULL si la columna no existe o está vacía.
- La sesión y el aula de cada fila deben existir; si no, `CargaError` con la línea y la columna (nunca el valor).
- Recibe una conexión ya migrada y no abre ni cierra transacciones (lo hace el orquestador de la carga).
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from extractor.csvio import FilaCsv, llegir_csv
from extractor.errors import CargaError
from extractor.load.comu import codis
from extractor.validacio import DIES, Validador

NOM_PARTIDA: str = "partida"

_FITXER = "proposta_partida.csv"
_COLUMNES = ("id_sessio", "dia", "h_ini", "aula")
_COL_DATA = "data"

_SQL_VERSIO = "INSERT INTO versio_horari (nom, mode, semestre, id_escenari) VALUES (?, 'complet', NULL, NULL)"
_SQL_ASSIGNACIO = "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data) VALUES (?, ?, ?, ?, ?, ?)"


@dataclass(frozen=True)
class _Assignacio:
    id_sessio: str
    dia: str
    h_ini: str
    aula: str | None
    data: str | None


@dataclass(frozen=True)
class _Referencies:
    sessions: frozenset[str]
    aules: frozenset[str]


def carregar_partida(conn: sqlite3.Connection, paquet: Path) -> int:
    """Inserta la versión `partida` y sus asignaciones; devuelve su `id_versio`."""
    assignacions = _llegir_assignacions(conn, paquet)
    id_versio = _inserir_versio(conn)
    conn.executemany(
        _SQL_ASSIGNACIO,
        [(id_versio, a.id_sessio, a.dia, a.h_ini, a.aula, a.data) for a in assignacions],
    )
    return id_versio


def _llegir_assignacions(conn: sqlite3.Connection, paquet: Path) -> list[_Assignacio]:
    referencies = _Referencies(
        sessions=codis(conn, "SELECT id_sessio FROM sessio"),
        aules=codis(conn, "SELECT codi FROM aula"),
    )
    validador = Validador(_FITXER)
    vistes: set[str] = set()
    assignacions: list[_Assignacio] = []
    for fila in llegir_csv(paquet / _FITXER, _COLUMNES):
        assignacio = _assignacio(validador, referencies, fila)
        if assignacio.id_sessio in vistes:
            raise CargaError(_FITXER, fila.linia, "id_sessio", "sesión repetida en la propuesta")
        vistes.add(assignacio.id_sessio)
        assignacions.append(assignacio)
    return assignacions


def _assignacio(validador: Validador, referencies: _Referencies, fila: FilaCsv) -> _Assignacio:
    id_sessio = validador.text(fila, "id_sessio")
    if id_sessio not in referencies.sessions:
        raise CargaError(_FITXER, fila.linia, "id_sessio", "la sesión no existe")
    aula = validador.text_opcional(fila, "aula")
    if aula is not None and aula not in referencies.aules:
        raise CargaError(_FITXER, fila.linia, "aula", "el aula no existe en el inventario")
    return _Assignacio(
        id_sessio=id_sessio,
        dia=validador.opcio(fila, "dia", DIES),
        h_ini=validador.hora(fila, "h_ini"),
        aula=aula,
        data=_data(validador, fila),
    )


def _data(validador: Validador, fila: FilaCsv) -> str | None:
    if _COL_DATA not in fila.valors or validador.text_opcional(fila, _COL_DATA) is None:
        return None
    return validador.data_iso(fila, _COL_DATA)


def _inserir_versio(conn: sqlite3.Connection) -> int:
    try:
        id_versio = conn.execute(_SQL_VERSIO, (NOM_PARTIDA,)).lastrowid
    except sqlite3.IntegrityError as error:
        raise CargaError(_FITXER, None, None, "la versión partida ya existe") from error
    if id_versio is None:
        raise CargaError(_FITXER, None, None, "no se ha podido crear la versión partida")
    return id_versio
