"""Carga de los catálogos del paquete: facultat, aula, titulacio, pla_estudis, pla_titulacio, calendari y escenari.

Recibe una conexión ya migrada y no abre ni cierra transacciones (lo hace el orquestador). Los errores de datos son
`CargaError` con el fichero relativo al paquete, la línea y la columna (o la clave del JSON); nunca el valor.

Plan `NOU` del grado nuevo (decisión 2 del plan): no está en `plans.csv`. Si existe
`escenaris/grau-nou-40/escenari.json`, se crea con la `descripcio` de ese JSON, `fitxer_origen = FITXER_NOU` y
`data_extraccio = DATA_EXTRACCIO_NOU` (fecha de generación del paquete), y se enlaza con las titulaciones de
`titulacions_curs` de `FITXER_NOU`.
"""

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from extractor.csvio import FilaCsv, llegir_csv
from extractor.errors import CargaError
from extractor.validacio import CURSOS, TIPUS_AULA, TIPUS_CALENDARI, Validador

FACULTAT: tuple[str, str] = ("EE", "Escola d'Enginyeria (UAB)")
AULES_EXTERNES: tuple[str, ...] = ("J/012", "J/102", "J/124", "B3/0021", "QC/1082")
ESPINES_NOMES_PLAB: frozenset[str] = frozenset({"Q5", "Q6"})
PLA_NOU: str = "NOU"
FITXER_NOU: str = "escenaris/grau-nou-40/sessions_extra.csv"
DATA_EXTRACCIO_NOU: str = "2026-11-05"

_FITXER_AULES = "aules.csv"
_FITXER_PLANS = "plans.csv"
_FITXER_SESSIONS = "sessions.csv"
_FITXER_CALENDARI = "calendari.csv"
_PATRO_SESSIONS_EXTRA = "escenaris/*/sessions_extra.csv"
_PATRO_ESCENARI = "escenaris/*/escenari.json"
_ESCENARI_NOU = PurePosixPath(FITXER_NOU).parent.name

_COLUMNES_AULES = ("aula", "edifici", "tipus", "descripcio", "capacitat", "ordinaria")
_COLUMNES_PLANS = ("pla", "titulacions", "descripcio", "fitxer_origen", "data_extraccio")
_COLUMNES_CALENDARI = ("data", "tipus", "h_ini", "h_fi", "motiu", "font")
_COL_TITULACIONS_CURS = "titulacions_curs"

_TIPUS_ORDINARIA = "Aules docents"
_MARCA_INTEGRAT = "integrat"
_CURS_MASTER = "M"
_SUFIX_PLA = re.compile(r"\s*\(pla [^)]*\)\s*$")

_Valors = tuple[str | int | None, ...]


@dataclass(frozen=True)
class _Pla:
    pla: str
    titulacions: tuple[str, ...]
    descripcio: str
    fitxer_origen: str
    data_extraccio: str


@dataclass(frozen=True)
class _Escenari:
    id_escenari: str
    fichero: str
    nom: str
    ficticia: int
    descripcio: str | None


def carregar_catalegs(conn: sqlite3.Connection, paquet: Path) -> None:
    """Inserta los catálogos del paquete en orden de FK; cualquier dato inválido lanza `CargaError`."""
    plans = _llegir_plans(paquet)
    cohorts = {fitxer: _llegir_cohorts(paquet, fitxer) for fitxer in _fitxers_sessions(paquet)}
    escenaris = _llegir_escenaris(paquet)
    escenari_nou = next((e for e in escenaris if e.id_escenari == _ESCENARI_NOU), None)
    titulacions_nou = {tit for tit, _ in cohorts.get(FITXER_NOU, [])} if escenari_nou else set()

    _inserir_facultat(conn)
    _inserir_aules(conn, paquet)
    _inserir_titulacions(conn, plans, cohorts)
    _inserir_plans(conn, plans, escenari_nou)
    _inserir_pla_titulacio(conn, plans, titulacions_nou)
    _inserir_calendari(conn, paquet)
    _inserir_escenaris(conn, escenaris)


# --- Lectura -----------------------------------------------------------------------------------------------------


def _llegir(paquet: Path, fitxer: str, columnes: Iterable[str]) -> list[FilaCsv]:
    """`llegir_csv` con el error referido a la ruta relativa al paquete (`llegir_csv` solo da el nombre)."""
    try:
        return llegir_csv(paquet / fitxer, columnes)
    except CargaError as error:
        raise CargaError(fitxer, error.linia, error.columna, error.motiu) from error


def _llegir_plans(paquet: Path) -> list[_Pla]:
    validador = Validador(_FITXER_PLANS)
    plans: list[_Pla] = []
    vistos: set[str] = set()
    for fila in _llegir(paquet, _FITXER_PLANS, _COLUMNES_PLANS):
        pla = validador.text(fila, "pla")
        if pla in vistos:
            raise CargaError(_FITXER_PLANS, fila.linia, "pla", "plan repetido")
        vistos.add(pla)
        titulacions = tuple(dict.fromkeys(validador.llista(fila, "titulacions", sep="+")))
        if not titulacions:
            raise CargaError(_FITXER_PLANS, fila.linia, "titulacions", "campo obligatorio vacío")
        plans.append(
            _Pla(
                pla=pla,
                titulacions=titulacions,
                descripcio=validador.text(fila, "descripcio"),
                fitxer_origen=validador.text(fila, "fitxer_origen"),
                data_extraccio=validador.data_dmy(fila, "data_extraccio"),
            )
        )
    return plans


def _fitxers_sessions(paquet: Path) -> list[str]:
    extres = sorted(path.relative_to(paquet).as_posix() for path in paquet.glob(_PATRO_SESSIONS_EXTRA))
    return [_FITXER_SESSIONS, *extres]


def _llegir_cohorts(paquet: Path, fitxer: str) -> list[tuple[str, str]]:
    """Pares (titulación, curso) de la columna `titulacions_curs` (`TIT:curs` separados por `|`)."""
    validador = Validador(fitxer)
    return [
        _cohort(fitxer, fila, element)
        for fila in _llegir(paquet, fitxer, (_COL_TITULACIONS_CURS,))
        for element in validador.llista(fila, _COL_TITULACIONS_CURS)
    ]


def _cohort(fitxer: str, fila: FilaCsv, element: str) -> tuple[str, str]:
    titulacio, separador, curs = element.partition(":")
    titulacio, curs = titulacio.strip(), curs.strip()
    if not separador or not titulacio or curs not in CURSOS:
        raise CargaError(fitxer, fila.linia, _COL_TITULACIONS_CURS, "no es TITULACIO:curs con un curso permitido")
    return titulacio, curs


def _llegir_escenaris(paquet: Path) -> list[_Escenari]:
    fitxers = sorted(paquet.glob(_PATRO_ESCENARI), key=lambda path: path.parent.name)
    return [_llegir_escenari(paquet, path) for path in fitxers]


def _llegir_escenari(paquet: Path, path: Path) -> _Escenari:
    fichero = path.relative_to(paquet).as_posix()
    dades = _llegir_json(path, fichero)
    return _Escenari(
        id_escenari=path.parent.name,
        fichero=fichero,
        nom=_clau_text(dades, fichero, "nom"),
        ficticia=_clau_bool(dades, fichero, "ficticia"),
        descripcio=_descripcio(dades, fichero),
    )


def _llegir_json(path: Path, fichero: str) -> Mapping[str, object]:
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


def _clau(dades: Mapping[str, object], fichero: str, clau: str) -> object:
    if clau not in dades:
        raise CargaError(fichero, None, clau, "falta la clave")
    return dades[clau]


def _clau_text(dades: Mapping[str, object], fichero: str, clau: str) -> str:
    valor = _clau(dades, fichero, clau)
    if not isinstance(valor, str) or not valor.strip():
        raise CargaError(fichero, None, clau, "se esperaba un texto no vacío")
    return valor


def _clau_bool(dades: Mapping[str, object], fichero: str, clau: str) -> int:
    valor = _clau(dades, fichero, clau)
    if not isinstance(valor, bool):
        raise CargaError(fichero, None, clau, "se esperaba true o false")
    return int(valor)


def _descripcio(dades: Mapping[str, object], fichero: str) -> str | None:
    """Texto tal cual, o lista de textos unida con un espacio; ausente o `null` → None."""
    valor = dades.get("descripcio")
    if valor is None or isinstance(valor, str):
        return valor
    if isinstance(valor, list):
        frases = [frase for frase in valor if isinstance(frase, str)]
        if len(frases) == len(valor):
            return " ".join(frases)
    raise CargaError(fichero, None, "descripcio", "se esperaba un texto o una lista de textos")


# --- Inserción ---------------------------------------------------------------------------------------------------


def _inserir_facultat(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO facultat (id_facultat, nom) VALUES (?, ?)", FACULTAT)


def _inserir_aules(conn: sqlite3.Connection, paquet: Path) -> None:
    validador = Validador(_FITXER_AULES)
    files: list[_Valors] = []
    inventari: set[str] = set()
    for fila in _llegir(paquet, _FITXER_AULES, _COLUMNES_AULES):
        codi = validador.text(fila, "aula")
        if codi in inventari:
            raise CargaError(_FITXER_AULES, fila.linia, "aula", "código de aula repetido")
        inventari.add(codi)
        files.append(_aula(validador, fila, codi))
    conn.executemany(
        "INSERT INTO aula (codi, id_facultat, edifici, tipus, capacitat, ordinaria, integrat, nomes_plab, descripcio)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        files,
    )
    conn.executemany(
        "INSERT INTO aula (codi, dins_aulari, admet_noves) VALUES (?, 0, 0)",
        [(codi,) for codi in AULES_EXTERNES if codi not in inventari],
    )


def _aula(validador: Validador, fila: FilaCsv, codi: str) -> _Valors:
    espina, barra, _ = codi.partition("/")
    if not barra or not espina:
        raise CargaError(_FITXER_AULES, fila.linia, "aula", "no tiene el formato ESPINA/NUMERO")
    tipus = validador.opcio(fila, "tipus", TIPUS_AULA)
    descripcio = validador.text_opcional(fila, "descripcio")
    capacitat = validador.enter(fila, "capacitat")
    ordinaria = validador.bool01(fila, "ordinaria")
    if ordinaria and tipus != _TIPUS_ORDINARIA:
        raise CargaError(_FITXER_AULES, fila.linia, "ordinaria", "solo puede valer 1 en aulas docentes")
    integrat = int(_MARCA_INTEGRAT in (descripcio or "").lower())
    nomes_plab = int(espina in ESPINES_NOMES_PLAB)
    edifici = validador.text_opcional(fila, "edifici")
    return (codi, FACULTAT[0], edifici, tipus, capacitat, ordinaria, integrat, nomes_plab, descripcio)


def _inserir_titulacions(
    conn: sqlite3.Connection, plans: Sequence[_Pla], cohorts: Mapping[str, Sequence[tuple[str, str]]]
) -> None:
    parells = [parell for llista in cohorts.values() for parell in llista]
    codis = {tit for pla in plans for tit in pla.titulacions} | {tit for tit, _ in parells}
    masters = {tit for tit, curs in parells if curs == _CURS_MASTER}
    noms = _noms_titulacio(plans)
    conn.executemany(
        "INSERT INTO titulacio (codi, nom, nivell, id_facultat) VALUES (?, ?, ?, ?)",
        [(codi, noms.get(codi), "master" if codi in masters else "grau", FACULTAT[0]) for codi in sorted(codis)],
    )


def _noms_titulacio(plans: Sequence[_Pla]) -> dict[str, str]:
    """Nombre de cada titulación: el primer plan de una sola titulación, sin el sufijo ` (pla …)`."""
    noms: dict[str, str] = {}
    for pla in plans:
        nom = _SUFIX_PLA.sub("", pla.descripcio, count=1)
        if len(pla.titulacions) == 1 and nom:
            noms.setdefault(pla.titulacions[0], nom)
    return noms


def _inserir_plans(conn: sqlite3.Connection, plans: Sequence[_Pla], escenari_nou: _Escenari | None) -> None:
    files: list[_Valors] = [(pla.pla, pla.descripcio, pla.fitxer_origen, pla.data_extraccio) for pla in plans]
    if escenari_nou is not None:
        if escenari_nou.descripcio is None:
            raise CargaError(escenari_nou.fichero, None, "descripcio", "falta la descripción del plan nuevo")
        files.append((PLA_NOU, escenari_nou.descripcio, FITXER_NOU, DATA_EXTRACCIO_NOU))
    conn.executemany(
        "INSERT INTO pla_estudis (pla, descripcio, fitxer_origen, data_extraccio) VALUES (?, ?, ?, ?)",
        files,
    )


def _inserir_pla_titulacio(conn: sqlite3.Connection, plans: Sequence[_Pla], titulacions_nou: Iterable[str]) -> None:
    files = [(pla.pla, tit) for pla in plans for tit in pla.titulacions]
    files.extend((PLA_NOU, tit) for tit in sorted(titulacions_nou))
    conn.executemany("INSERT INTO pla_titulacio (pla, titulacio) VALUES (?, ?)", files)


def _inserir_calendari(conn: sqlite3.Connection, paquet: Path) -> None:
    validador = Validador(_FITXER_CALENDARI)
    conn.executemany(
        "INSERT INTO calendari (data, tipus, h_ini, h_fi, motiu, font) VALUES (?, ?, ?, ?, ?, ?)",
        [_dia_calendari(validador, fila) for fila in _llegir(paquet, _FITXER_CALENDARI, _COLUMNES_CALENDARI)],
    )


def _dia_calendari(validador: Validador, fila: FilaCsv) -> _Valors:
    data = validador.data_iso(fila, "data")
    tipus = validador.opcio(fila, "tipus", TIPUS_CALENDARI)
    h_ini = validador.hora_opcional(fila, "h_ini")
    h_fi = validador.hora_opcional(fila, "h_fi")
    if (h_ini is None) != (h_fi is None):
        raise CargaError(_FITXER_CALENDARI, fila.linia, "h_fi", "h_ini y h_fi van las dos o ninguna")
    if h_ini is not None and h_fi is not None and h_fi <= h_ini:
        raise CargaError(_FITXER_CALENDARI, fila.linia, "h_fi", "h_fi debe ser posterior a h_ini")
    return (data, tipus, h_ini, h_fi, validador.text(fila, "motiu"), validador.text(fila, "font"))


def _inserir_escenaris(conn: sqlite3.Connection, escenaris: Sequence[_Escenari]) -> None:
    noms: set[str] = set()
    for escenari in escenaris:
        if escenari.nom in noms:
            raise CargaError(escenari.fichero, None, "nom", "nombre de escenario repetido")
        noms.add(escenari.nom)
    conn.executemany(
        "INSERT INTO escenari (id_escenari, nom, ficticia, descripcio) VALUES (?, ?, ?, ?)",
        [(e.id_escenari, e.nom, e.ficticia, e.descripcio) for e in escenaris],
    )
