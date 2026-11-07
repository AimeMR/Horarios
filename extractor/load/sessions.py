"""Carga de un fichero de sesiones (`sessions.csv` o el `sessions_extra.csv` de un escenario) y, opcionalmente, de
`activitats.csv`.

Tablas, en este orden: `assignatura`, `assignatura_pla`, `cohort`, `assignatura_cohort`, `grup` (+ 2ª pasada para
`id_grup_teoria`), `profe`, `docencia`, `activitat` (solo con `fitxer_activitats`) y `sessio`.

- Requiere `carregar_catalegs` ya ejecutado: las aulas, los planes y las titulaciones referenciados deben existir.
- No abre ni cierra transacciones (lo hace el orquestador de la carga).
- Los atributos de asignatura y de grupo deben ser iguales en todas sus filas; si cambian, `CargaError` con la línea
  de la fila que discrepa y la columna.
- Se pierden `semestre` (el esquema lo calcula por fecha) y `h_fi` (se comprueba que vale `h_ini + durada_min`).
"""

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from extractor.csvio import FilaCsv, llegir_csv
from extractor.errors import CargaError
from extractor.linia import linia, numero, triar_teoria
from extractor.validacio import ALUMNES_ORIGEN, CURSOS, DC, DIES, TIPUS_GRUP, TORNS, Validador, sumar_minuts

VIGENT_DES_DE: str = "2026-09-01"
ALUMNES_ORIGEN_DEFECTE: str = "sigma"

_SEPARADOR_ID_GRUP = "·"
_TIPUS_TEORIA = "TE"
_TORN_PER_CURS: dict[str, str] = {"1r": "mati", "2n": "mati", "3r": "tarda", "4t": "tarda", "M": "tarda"}
_COL_ALUMNES_ORIGEN = "alumnes_origen"
_COL_SENSE_ESPAI = "sense_espai"
_COL_TITULACIONS = "titulacions_curs"

_COLUMNES_SESSIONS = (
    "id_sessio",
    "activitat_id",
    "id_compartida",
    "codi",
    "assignatura",
    "tipus",
    "grup",
    "data",
    "setmana",
    "dia",
    "h_ini",
    "h_fi",
    "durada_min",
    "alumnes",
    "capacitat_grup",
    "aula_partida",
    "aules_addicionals_partida",
    "plans",
    _COL_TITULACIONS,
    "dc",
    "torn_requerit",
    "fixada",
    "docents",
)
_COLUMNES_ACTIVITATS = (
    "activitat_id",
    "codi",
    "grup",
    "dia",
    "h_ini",
    "h_fi",
    "setmana_primera",
    "setmana_ultima",
    "n_sessions",
)

_MOTIU_ASSIGNATURA = "cambia dentro de la asignatura"
_MOTIU_GRUP = "cambia dentro del grupo"

_SQL_ASSIGNATURA = "INSERT INTO assignatura (codi, nom) VALUES (?, ?)"
_SQL_ASSIGNATURA_PLA = "INSERT INTO assignatura_pla (codi, pla) VALUES (?, ?)"
_SQL_COHORT = "INSERT OR IGNORE INTO cohort (id_cohort, titulacio, curs, torn_requerit) VALUES (?, ?, ?, ?)"
_SQL_ASSIGNATURA_COHORT = "INSERT INTO assignatura_cohort (codi, id_cohort) VALUES (?, ?)"
_SQL_GRUP = (
    "INSERT INTO grup (id_grup, codi, grup, tipus, numero, linia, alumnes, alumnes_origen, capacitat_grup, "
    "sense_espai, fixada_motiu, torn_requerit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_SQL_GRUP_TEORIA = "UPDATE grup SET id_grup_teoria = ? WHERE id_grup = ?"
_SQL_PROFE = "INSERT OR IGNORE INTO profe (id_profe) VALUES (?)"
_SQL_DOCENCIA = "INSERT INTO docencia (id_profe, id_grup, vigent_des_de) VALUES (?, ?, ?)"
_SQL_ACTIVITAT = (
    "INSERT INTO activitat (activitat_id, id_grup, dia, h_ini, h_fi, setmana_primera, setmana_ultima, n_sessions) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
_SQL_SESSIO = (
    "INSERT INTO sessio (id_sessio, activitat_id, id_grup, id_escenari, id_compartida, dc, setmana, durada_min, "
    "data_partida, dia_partida, h_ini_partida, aula_partida, aules_addicionals_partida) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

Atributs = tuple[tuple[str, object], ...]
FilaSql = tuple[object, ...]


class _AmbAtributs(Protocol):
    def atributs(self) -> Atributs: ...


@dataclass(frozen=True)
class _Cohort:
    titulacio: str
    curs: str

    @property
    def id_cohort(self) -> str:
        return f"{self.titulacio}:{self.curs}"

    @property
    def torn_requerit(self) -> str | None:
        """Regla 1: `1r`, `2n` → mati; `3r`, `4t`, `M` → tarda; `?` → sin turno."""
        return _TORN_PER_CURS.get(self.curs)


@dataclass(frozen=True)
class _Assignatura:
    codi: str
    nom: str
    plans: tuple[str, ...]
    cohorts: tuple[_Cohort, ...]

    def atributs(self) -> Atributs:
        return (("assignatura", self.nom), ("plans", self.plans), (_COL_TITULACIONS, self.cohorts))


@dataclass(frozen=True)
class _Grup:
    codi: str
    grup: str
    tipus: str
    alumnes: int
    alumnes_origen: str
    capacitat_grup: int | None
    sense_espai: int
    fixada_motiu: str | None
    torn_requerit: str
    docents: tuple[str, ...]

    @property
    def id_grup(self) -> str:
        return _id_grup(self.codi, self.grup)

    @property
    def numero(self) -> str:
        return numero(self.grup)

    @property
    def linia(self) -> str:
        return linia(self.tipus, self.grup)

    def atributs(self) -> Atributs:
        return (
            ("tipus", self.tipus),
            ("alumnes", self.alumnes),
            (_COL_ALUMNES_ORIGEN, self.alumnes_origen),
            ("capacitat_grup", self.capacitat_grup),
            (_COL_SENSE_ESPAI, self.sense_espai),
            ("fixada", self.fixada_motiu),
            ("torn_requerit", self.torn_requerit),
            ("docents", self.docents),
        )


@dataclass(frozen=True)
class _Sessio:
    id_sessio: str
    activitat_id: str | None
    id_grup: str
    id_compartida: str | None
    dc: str | None
    setmana: str
    durada_min: int
    data: str
    dia: str
    h_ini: str
    aula: str | None
    aules_addicionals: str | None


@dataclass(frozen=True)
class _FilaSessio:
    linia: int
    assignatura: _Assignatura
    grup: _Grup
    sessio: _Sessio


@dataclass(frozen=True)
class _Activitat:
    activitat_id: str
    id_grup: str
    dia: str
    h_ini: str
    h_fi: str
    setmana_primera: str
    setmana_ultima: str
    n_sessions: int


@dataclass(frozen=True)
class _Contingut:
    assignatures: tuple[_Assignatura, ...]
    grups: tuple[_Grup, ...]
    files: tuple[_FilaSessio, ...]


@dataclass(frozen=True)
class _Referencies:
    aules: frozenset[str]
    plans: frozenset[str]
    titulacions: frozenset[str]


@dataclass(frozen=True)
class _Lector:
    fichero: str
    validador: Validador

    def error(self, fila: FilaCsv, col: str, motiu: str) -> CargaError:
        return CargaError(self.fichero, fila.linia, col, motiu)


def carregar_sessions(
    conn: sqlite3.Connection,
    paquet: Path,
    fitxer_sessions: str,
    fitxer_activitats: str | None,
    id_escenari: str | None,
) -> None:
    """Carga `fitxer_sessions` (y `fitxer_activitats` si se da); las sesiones llevan `id_escenari`."""
    contingut = _agrupar(fitxer_sessions, _llegir_sessions(conn, paquet, fitxer_sessions))
    _inserir_assignatures(conn, fitxer_sessions, contingut.assignatures)
    _inserir_grups(conn, fitxer_sessions, contingut.grups)
    if fitxer_activitats is not None:
        _carregar_activitats(conn, paquet, fitxer_activitats)
    _inserir_sessions(conn, fitxer_sessions, contingut.files, id_escenari)


# --- Lectura y validación de sessions ------------------------------------------------------------------------


def _llegir_sessions(conn: sqlite3.Connection, paquet: Path, fitxer: str) -> list[_FilaSessio]:
    referencies = _Referencies(
        aules=_codis(conn, "SELECT codi FROM aula"),
        plans=_codis(conn, "SELECT pla FROM pla_estudis"),
        titulacions=_codis(conn, "SELECT codi FROM titulacio"),
    )
    lector = _Lector(fitxer, Validador(fitxer))
    return [_fila_sessio(lector, referencies, fila) for fila in llegir_csv(paquet / fitxer, _COLUMNES_SESSIONS)]


def _fila_sessio(lector: _Lector, referencies: _Referencies, fila: FilaCsv) -> _FilaSessio:
    codi = lector.validador.text(fila, "codi")
    assignatura = _assignatura(lector, referencies, fila, codi)
    grup = _grup(lector, fila, codi)
    sessio = _sessio(lector, referencies, fila, grup.id_grup)
    return _FilaSessio(linia=fila.linia, assignatura=assignatura, grup=grup, sessio=sessio)


def _assignatura(lector: _Lector, referencies: _Referencies, fila: FilaCsv, codi: str) -> _Assignatura:
    plans = _sense_repetits(lector, fila, "plans", lector.validador.llista(fila, "plans"))
    for pla in plans:
        if pla not in referencies.plans:
            raise lector.error(fila, "plans", "el plan de estudios no existe")
    return _Assignatura(
        codi=codi,
        nom=lector.validador.text(fila, "assignatura"),
        plans=plans,
        cohorts=_cohorts(lector, referencies, fila),
    )


def _cohorts(lector: _Lector, referencies: _Referencies, fila: FilaCsv) -> tuple[_Cohort, ...]:
    cohorts: list[_Cohort] = []
    for valor in lector.validador.llista(fila, _COL_TITULACIONS):
        titulacio, separador, curs = valor.partition(":")
        if not separador or not titulacio or curs not in CURSOS:
            raise lector.error(fila, _COL_TITULACIONS, "no tiene el formato TITULACIO:curs con un curso permitido")
        if titulacio not in referencies.titulacions:
            raise lector.error(fila, _COL_TITULACIONS, "la titulación no existe")
        cohorts.append(_Cohort(titulacio=titulacio, curs=curs))
    return _sense_repetits(lector, fila, _COL_TITULACIONS, cohorts)


def _grup(lector: _Lector, fila: FilaCsv, codi: str) -> _Grup:
    validador = lector.validador
    tipus = validador.opcio(fila, "tipus", TIPUS_GRUP)
    grup = validador.text(fila, "grup")
    _comprovar_prefix(lector, fila, tipus, grup)
    return _Grup(
        codi=codi,
        grup=grup,
        tipus=tipus,
        alumnes=validador.enter(fila, "alumnes"),
        alumnes_origen=_alumnes_origen(validador, fila),
        capacitat_grup=validador.enter_opcional(fila, "capacitat_grup"),
        sense_espai=_sense_espai(validador, fila),
        fixada_motiu=validador.text_opcional(fila, "fixada"),
        torn_requerit=validador.opcio(fila, "torn_requerit", TORNS),
        docents=_sense_repetits(lector, fila, "docents", validador.llista(fila, "docents")),
    )


def _comprovar_prefix(lector: _Lector, fila: FilaCsv, tipus: str, grup: str) -> None:
    prefix, separador, num = grup.partition("/")
    if not separador or not num or "/" in num or prefix not in TIPUS_GRUP:
        raise lector.error(fila, "grup", "no tiene el formato TIPUS/NUMERO")
    if prefix != tipus:
        raise lector.error(fila, "tipus", "no coincide con el prefijo del grupo")


def _alumnes_origen(validador: Validador, fila: FilaCsv) -> str:
    if _COL_ALUMNES_ORIGEN not in fila.valors:
        return ALUMNES_ORIGEN_DEFECTE
    return validador.opcio(fila, _COL_ALUMNES_ORIGEN, ALUMNES_ORIGEN)


def _sense_espai(validador: Validador, fila: FilaCsv) -> int:
    if _COL_SENSE_ESPAI not in fila.valors:
        return 0
    return validador.bool01(fila, _COL_SENSE_ESPAI)


def _sessio(lector: _Lector, referencies: _Referencies, fila: FilaCsv, id_grup: str) -> _Sessio:
    validador = lector.validador
    h_ini = validador.hora(fila, "h_ini")
    durada_min = validador.enter(fila, "durada_min", minim=1)
    _comprovar_h_fi(lector, fila, h_ini, durada_min)
    return _Sessio(
        id_sessio=validador.text(fila, "id_sessio"),
        activitat_id=validador.text_opcional(fila, "activitat_id"),
        id_grup=id_grup,
        id_compartida=validador.text_opcional(fila, "id_compartida"),
        dc=validador.opcio_opcional(fila, "dc", DC),
        setmana=validador.setmana(fila, "setmana"),
        durada_min=durada_min,
        data=validador.data_iso(fila, "data"),
        dia=validador.opcio(fila, "dia", DIES),
        h_ini=h_ini,
        aula=_aula(lector, referencies, fila, "aula_partida"),
        aules_addicionals=_aula(lector, referencies, fila, "aules_addicionals_partida"),
    )


def _comprovar_h_fi(lector: _Lector, fila: FilaCsv, h_ini: str, durada_min: int) -> None:
    h_fi = lector.validador.hora(fila, "h_fi")
    try:
        esperada = sumar_minuts(h_ini, durada_min)
    except ValueError as error:
        raise lector.error(fila, "durada_min", "la sesión acaba fuera del día") from error
    if h_fi != esperada:
        raise lector.error(fila, "h_fi", "no cuadra con h_ini + durada_min")


def _aula(lector: _Lector, referencies: _Referencies, fila: FilaCsv, col: str) -> str | None:
    codi = lector.validador.text_opcional(fila, col)
    if codi is not None and codi not in referencies.aules:
        raise lector.error(fila, col, "el aula no existe en el inventario")
    return codi


def _sense_repetits[T](lector: _Lector, fila: FilaCsv, col: str, valors: list[T]) -> tuple[T, ...]:
    if len(set(valors)) != len(valors):
        raise lector.error(fila, col, "tiene elementos repetidos")
    return tuple(valors)


# --- Agrupación por asignatura y grupo -----------------------------------------------------------------------


def _agrupar(fichero: str, files: list[_FilaSessio]) -> _Contingut:
    assignatures: dict[str, _Assignatura] = {}
    grups: dict[str, _Grup] = {}
    for fila in files:
        _registrar(fichero, fila.linia, assignatures, fila.assignatura.codi, fila.assignatura, _MOTIU_ASSIGNATURA)
        _registrar(fichero, fila.linia, grups, fila.grup.id_grup, fila.grup, _MOTIU_GRUP)
    return _Contingut(assignatures=tuple(assignatures.values()), grups=tuple(grups.values()), files=tuple(files))


def _registrar[R: _AmbAtributs](
    fichero: str, linia_fila: int, vistos: dict[str, R], clau: str, registre: R, motiu: str
) -> None:
    """Guarda la primera aparición de `clau`; las siguientes deben tener los mismos atributos."""
    primer = vistos.setdefault(clau, registre)
    for (columna, valor), (_, valor_primer) in zip(registre.atributs(), primer.atributs(), strict=True):
        if valor != valor_primer:
            raise CargaError(fichero, linia_fila, columna, motiu)


# --- Inserción -----------------------------------------------------------------------------------------------


def _inserir_assignatures(conn: sqlite3.Connection, fichero: str, assignatures: Sequence[_Assignatura]) -> None:
    _inserir(conn, fichero, "assignatura", _SQL_ASSIGNATURA, [(a.codi, a.nom) for a in assignatures])
    _inserir(
        conn, fichero, "assignatura_pla", _SQL_ASSIGNATURA_PLA, [(a.codi, pla) for a in assignatures for pla in a.plans]
    )
    _inserir(
        conn,
        fichero,
        "cohort",
        _SQL_COHORT,
        [(c.id_cohort, c.titulacio, c.curs, c.torn_requerit) for a in assignatures for c in a.cohorts],
    )
    _inserir(
        conn,
        fichero,
        "assignatura_cohort",
        _SQL_ASSIGNATURA_COHORT,
        [(a.codi, c.id_cohort) for a in assignatures for c in a.cohorts],
    )


def _inserir_grups(conn: sqlite3.Connection, fichero: str, grups: Sequence[_Grup]) -> None:
    _inserir(conn, fichero, "grup", _SQL_GRUP, [_fila_grup(g) for g in grups])
    _inserir(conn, fichero, "grup", _SQL_GRUP_TEORIA, _teories(grups))
    _inserir(conn, fichero, "profe", _SQL_PROFE, [(profe,) for g in grups for profe in g.docents])
    _inserir(
        conn,
        fichero,
        "docencia",
        _SQL_DOCENCIA,
        [(profe, g.id_grup, VIGENT_DES_DE) for g in grups for profe in g.docents],
    )


def _fila_grup(grup: _Grup) -> FilaSql:
    return (
        grup.id_grup,
        grup.codi,
        grup.grup,
        grup.tipus,
        grup.numero,
        grup.linia,
        grup.alumnes,
        grup.alumnes_origen,
        grup.capacitat_grup,
        grup.sense_espai,
        grup.fixada_motiu,
        grup.torn_requerit,
    )


def _teories(grups: Sequence[_Grup]) -> list[FilaSql]:
    """Filas `(id_grup_teoria, id_grup)` de los subgrupos con teoría, con el criterio del verificador."""
    teories: dict[str, list[str]] = {}
    for grup in grups:
        if grup.tipus == _TIPUS_TEORIA:
            teories.setdefault(grup.codi, []).append(grup.grup)
    files: list[FilaSql] = []
    for grup in grups:
        if grup.tipus == _TIPUS_TEORIA:
            continue
        teoria = triar_teoria(grup.linia, teories.get(grup.codi, []), numero_subgrup=grup.numero)
        if teoria is not None:
            files.append((_id_grup(grup.codi, teoria), grup.id_grup))
    return files


def _carregar_activitats(conn: sqlite3.Connection, paquet: Path, fitxer: str) -> None:
    lector = _Lector(fitxer, Validador(fitxer))
    grups = _codis(conn, "SELECT id_grup FROM grup")
    activitats = [_activitat(lector, grups, fila) for fila in llegir_csv(paquet / fitxer, _COLUMNES_ACTIVITATS)]
    _inserir(
        conn,
        fitxer,
        "activitat",
        _SQL_ACTIVITAT,
        [
            (a.activitat_id, a.id_grup, a.dia, a.h_ini, a.h_fi, a.setmana_primera, a.setmana_ultima, a.n_sessions)
            for a in activitats
        ],
    )


def _activitat(lector: _Lector, grups: frozenset[str], fila: FilaCsv) -> _Activitat:
    validador = lector.validador
    id_grup = _id_grup(validador.text(fila, "codi"), validador.text(fila, "grup"))
    if id_grup not in grups:
        raise lector.error(fila, "grup", "el grupo no existe en las sesiones")
    h_ini = validador.hora(fila, "h_ini")
    h_fi = validador.hora(fila, "h_fi")
    if h_fi <= h_ini:
        raise lector.error(fila, "h_fi", "no es posterior a h_ini")
    return _Activitat(
        activitat_id=validador.text(fila, "activitat_id"),
        id_grup=id_grup,
        dia=validador.opcio(fila, "dia", DIES),
        h_ini=h_ini,
        h_fi=h_fi,
        setmana_primera=validador.setmana(fila, "setmana_primera"),
        setmana_ultima=validador.setmana(fila, "setmana_ultima"),
        n_sessions=validador.enter(fila, "n_sessions", minim=1),
    )


def _inserir_sessions(
    conn: sqlite3.Connection, fichero: str, files: Sequence[_FilaSessio], id_escenari: str | None
) -> None:
    activitats = _codis(conn, "SELECT activitat_id FROM activitat")
    for fila in files:
        if fila.sessio.activitat_id is not None and fila.sessio.activitat_id not in activitats:
            raise CargaError(fichero, fila.linia, "activitat_id", "la actividad no existe")
    _inserir(conn, fichero, "sessio", _SQL_SESSIO, [_fila_sessio_sql(fila.sessio, id_escenari) for fila in files])


def _fila_sessio_sql(sessio: _Sessio, id_escenari: str | None) -> FilaSql:
    return (
        sessio.id_sessio,
        sessio.activitat_id,
        sessio.id_grup,
        id_escenari,
        sessio.id_compartida,
        sessio.dc,
        sessio.setmana,
        sessio.durada_min,
        sessio.data,
        sessio.dia,
        sessio.h_ini,
        sessio.aula,
        sessio.aules_addicionals,
    )


# --- Utilidades ----------------------------------------------------------------------------------------------


def _id_grup(codi: str, grup: str) -> str:
    return f"{codi}{_SEPARADOR_ID_GRUP}{grup}"


def _codis(conn: sqlite3.Connection, sql: str) -> frozenset[str]:
    """Primera columna de una consulta fija (sin parámetros) como conjunto de textos."""
    return frozenset(str(fila[0]) for fila in conn.execute(sql))


def _inserir(conn: sqlite3.Connection, fichero: str, taula: str, sql: str, files: Iterable[FilaSql]) -> None:
    """`executemany` en un solo lote; una clave repetida o una FK rota se traduce en `CargaError` sin valores."""
    try:
        conn.executemany(sql, files)
    except sqlite3.IntegrityError as error:
        raise CargaError(fichero, None, None, f"clave repetida o referencia inexistente al cargar {taula}") from error
