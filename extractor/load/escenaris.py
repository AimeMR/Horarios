"""Carga de los escenarios del paquete: sesiones del grado nuevo, aulas cerradas, cancelaciones y cambios de alumnos.

Para cada `escenaris/<dir>/escenari.json` (la fila de `escenari` ya la inserta `carregar_catalegs`):

- `sessions_extra` (opcional): nombre de un CSV de la misma carpeta; se carga con `carregar_sessions` y sus sesiones
  llevan `id_escenari = <dir>`. Es lo que aporta el grado nuevo (plan `NOU`, decisión 2 del plan: `pla_estudis` y
  `pla_titulacio` de `NOU` los crea `carregar_catalegs` a partir de este mismo JSON). Los JSON y su fichero extra se
  leen con `comu.llegir_escenaris`, la misma función que usa `carregar_catalegs`.
- `aules_tancades` → `tancament_aula` (`aula`, `data_ini`, `data_fi`; horas y `motiu` NULL: el JSON no los da).
- `cancellades` → `cancellacio` (`id_sessio`, `recuperar_fins`).
- `alumnes` → `canvi_alumnes` (`codi` + `grup` → `id_grup`, `alumnes`).

Las claves ausentes valen como listas vacías. Recibe una conexión ya migrada y no abre ni cierra transacciones. Los
errores son `CargaError(<ruta relativa del JSON>, None, <clave de primer nivel>, motiu)`; nunca el valor.
"""

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from extractor.csvio import FilaCsv
from extractor.errors import CargaError
from extractor.load.comu import EscenariJson, id_grup, llegir_escenaris
from extractor.load.sessions import carregar_sessions
from extractor.validacio import Validador

_CLAU_TANCADES = "aules_tancades"
_CLAU_CANCELLADES = "cancellades"
_CLAU_ALUMNES = "alumnes"

_SQL_EXISTEIX_AULA = "SELECT 1 FROM aula WHERE codi = ?"
_SQL_EXISTEIX_SESSIO = "SELECT 1 FROM sessio WHERE id_sessio = ?"
_SQL_EXISTEIX_GRUP = "SELECT 1 FROM grup WHERE id_grup = ?"
_SQL_TANCAMENT = "INSERT INTO tancament_aula (id_escenari, aula, data_ini, data_fi) VALUES (?, ?, ?, ?)"
_SQL_CANCELLACIO = "INSERT INTO cancellacio (id_escenari, id_sessio, recuperar_fins) VALUES (?, ?, ?)"
_SQL_CANVI_ALUMNES = "INSERT INTO canvi_alumnes (id_escenari, id_grup, alumnes) VALUES (?, ?, ?)"

_Element = Mapping[str, object]


@dataclass(frozen=True)
class _Lloc:
    """Dónde se señala un error: el JSON relativo al paquete y la clave de primer nivel."""

    fichero: str
    clau: str

    def error(self, motiu: str) -> CargaError:
        return CargaError(self.fichero, None, self.clau, motiu)


@dataclass(frozen=True)
class _Tancament:
    aula: str
    data_ini: str
    data_fi: str


@dataclass(frozen=True)
class _Cancellacio:
    id_sessio: str
    recuperar_fins: str


@dataclass(frozen=True)
class _CanviAlumnes:
    id_grup: str
    alumnes: int


@dataclass(frozen=True)
class _Escenari:
    id_escenari: str
    fichero: str
    sessions_extra: str | None
    tancaments: tuple[_Tancament, ...]
    cancellacions: tuple[_Cancellacio, ...]
    canvis: tuple[_CanviAlumnes, ...]


def carregar_escenaris(conn: sqlite3.Connection, paquet: Path) -> None:
    """Carga cada escenario en orden alfabético de carpeta; cualquier dato inválido lanza `CargaError`."""
    for escenari in [_escenari(escenari_json) for escenari_json in llegir_escenaris(paquet)]:
        _carregar_escenari(conn, paquet, escenari)


# --- Lectura y validación del JSON ---------------------------------------------------------------------------


def _escenari(escenari: EscenariJson) -> _Escenari:
    dades, fichero = escenari.dades, escenari.fichero
    return _Escenari(
        id_escenari=escenari.id_escenari,
        fichero=fichero,
        sessions_extra=escenari.sessions_extra,
        tancaments=_llista(dades, _Lloc(fichero, _CLAU_TANCADES), _tancament),
        cancellacions=_sense_repetits(
            _llista(dades, _Lloc(fichero, _CLAU_CANCELLADES), _cancellacio),
            lambda c: c.id_sessio,
            _Lloc(fichero, _CLAU_CANCELLADES),
        ),
        canvis=_sense_repetits(
            _llista(dades, _Lloc(fichero, _CLAU_ALUMNES), _canvi_alumnes),
            lambda c: c.id_grup,
            _Lloc(fichero, _CLAU_ALUMNES),
        ),
    )


def _llista[T](dades: _Element, lloc: _Lloc, convertir: Callable[[_Element, _Lloc], T]) -> tuple[T, ...]:
    """Lista de objetos de la clave `lloc.clau`; ausente o `null` → vacía."""
    valor = dades.get(lloc.clau)
    if valor is None:
        return ()
    if not isinstance(valor, list):
        raise lloc.error("se esperaba una lista de objetos")
    elements: list[T] = []
    for element in valor:
        if not isinstance(element, dict):
            raise lloc.error("cada elemento debe ser un objeto")
        elements.append(convertir(element, lloc))
    return tuple(elements)


def _tancament(element: _Element, lloc: _Lloc) -> _Tancament:
    data_ini = _data(element, lloc, "data_ini")
    data_fi = _data(element, lloc, "data_fi")
    if data_fi < data_ini:
        raise lloc.error("data_fi no puede ser anterior a data_ini")
    return _Tancament(aula=_text(element, lloc, "aula"), data_ini=data_ini, data_fi=data_fi)


def _cancellacio(element: _Element, lloc: _Lloc) -> _Cancellacio:
    return _Cancellacio(
        id_sessio=_text(element, lloc, "id_sessio"), recuperar_fins=_data(element, lloc, "recuperar_fins")
    )


def _canvi_alumnes(element: _Element, lloc: _Lloc) -> _CanviAlumnes:
    grup = id_grup(_text(element, lloc, "codi"), _text(element, lloc, "grup"))
    return _CanviAlumnes(id_grup=grup, alumnes=_enter(element, lloc, "alumnes"))


def _text(element: _Element, lloc: _Lloc, camp: str) -> str:
    valor = element.get(camp)
    if not isinstance(valor, str) or not valor.strip():
        raise lloc.error(f"el campo {camp} debe ser un texto no vacío")
    return valor.strip()


def _enter(element: _Element, lloc: _Lloc, camp: str) -> int:
    valor = element.get(camp)
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise lloc.error(f"el campo {camp} debe ser un entero no negativo")
    return valor


def _data(element: _Element, lloc: _Lloc, camp: str) -> str:
    """Fecha AAAA-MM-DD con la misma regla que los CSV (`Validador.data_iso`)."""
    text = _text(element, lloc, camp)
    try:
        return Validador(lloc.fichero).data_iso(FilaCsv(linia=0, valors={camp: text}), camp)
    except CargaError as error:
        raise lloc.error(f"el campo {camp}: {error.motiu}") from error


def _sense_repetits[T](elements: tuple[T, ...], clau: Callable[[T], str], lloc: _Lloc) -> tuple[T, ...]:
    claus = [clau(element) for element in elements]
    if len(set(claus)) != len(claus):
        raise lloc.error("tiene elementos repetidos")
    return elements


# --- Comprobación de referencias e inserción ----------------------------------------------------------------


def _carregar_escenari(conn: sqlite3.Connection, paquet: Path, escenari: _Escenari) -> None:
    if escenari.sessions_extra is not None:
        carregar_sessions(conn, paquet, escenari.sessions_extra, None, id_escenari=escenari.id_escenari)
    _comprovar_referencies(conn, escenari)
    conn.executemany(
        _SQL_TANCAMENT,
        [(escenari.id_escenari, t.aula, t.data_ini, t.data_fi) for t in escenari.tancaments],
    )
    conn.executemany(
        _SQL_CANCELLACIO,
        [(escenari.id_escenari, c.id_sessio, c.recuperar_fins) for c in escenari.cancellacions],
    )
    conn.executemany(
        _SQL_CANVI_ALUMNES,
        [(escenari.id_escenari, c.id_grup, c.alumnes) for c in escenari.canvis],
    )


def _comprovar_referencies(conn: sqlite3.Connection, escenari: _Escenari) -> None:
    fichero = escenari.fichero
    _comprovar(
        conn,
        _SQL_EXISTEIX_AULA,
        [t.aula for t in escenari.tancaments],
        _Lloc(fichero, _CLAU_TANCADES),
        "el aula no existe en el inventario",
    )
    _comprovar(
        conn,
        _SQL_EXISTEIX_SESSIO,
        [c.id_sessio for c in escenari.cancellacions],
        _Lloc(fichero, _CLAU_CANCELLADES),
        "la sesión no existe",
    )
    _comprovar(
        conn,
        _SQL_EXISTEIX_GRUP,
        [c.id_grup for c in escenari.canvis],
        _Lloc(fichero, _CLAU_ALUMNES),
        "el grupo no existe",
    )


def _comprovar(conn: sqlite3.Connection, sql: str, valors: Sequence[str], lloc: _Lloc, motiu: str) -> None:
    """Cada valor debe existir según la consulta fija `sql` (un parámetro); si no, error sin el valor."""
    for valor in valors:
        if conn.execute(sql, (valor,)).fetchone() is None:
            raise lloc.error(motiu)
