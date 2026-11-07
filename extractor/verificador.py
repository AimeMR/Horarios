"""Lanza el verificador oficial (`python -m horaris check`) sobre una versión exportada y guarda su veredicto.

Seguridad: los nombres de versión y de escenario se validan con `fullmatch` antes de construir rutas o lanzar nada;
el proceso hijo se lanza con una lista de argumentos, sin shell y con timeout. Los mensajes de error nunca incluyen
la salida del proceso (puede llevar datos del paquete).
"""

# B404 se silencia en `import subprocess`: solo lanza sys.executable con lista de argumentos, sin shell y con
# entradas validadas (ver _executa).
import json
import os
import re
import sqlite3
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path

from extractor.errors import VerificadorError
from extractor.export import exportar, validar_nom_versio

VEREDICTES: frozenset[str] = frozenset({"VALIDA", "VALIDA AMB RELAXACIONS DECLARADES", "NO VALIDA"})
PATRO_ESCENARI: re.Pattern[str] = re.compile(r"[a-z0-9-]{1,64}")

_CODIS_ESPERATS: frozenset[int] = frozenset({0, 1})
_MODE_NOMES_AULES = "nomes_aules"

_LLEGIR_VERSIO = (
    "SELECT v.id_versio, v.semestre, v.mode, v.id_escenari, v.id_versio_referencia, r.nom "
    "FROM versio_horari v LEFT JOIN versio_horari r ON r.id_versio = v.id_versio_referencia WHERE v.nom = ?"
)
_GUARDAR_RESULTAT = "UPDATE versio_horari SET veredicte = ?, informe_json = ? WHERE id_versio = ?"


@dataclass(frozen=True)
class ResultatVerificacio:
    codi_sortida: int
    veredicte: str
    proposta: Path
    informe: Path
    violacions: Path


@dataclass(frozen=True)
class _Versio:
    id_versio: int
    semestre: int | None
    nomes_aules: bool
    id_escenari: str | None
    nom_referencia: str | None


def verificar(
    conn: sqlite3.Connection,
    versio: str,
    paquet: Path,
    dir_verificador: Path,
    dir_sortida: Path,
    timeout_s: float = 900.0,
) -> ResultatVerificacio:
    """Exporta `versio`, la pasa por el verificador y guarda `veredicte` e `informe_json` en `versio_horari`."""
    validar_nom_versio(versio)
    dades = _llegir_versio(conn, versio)
    arrel = paquet.resolve()
    carpeta_escenari = None if dades.id_escenari is None else _carpeta_escenari(arrel, dades.id_escenari)
    sortida = dir_sortida.absolute()
    proposta = sortida / f"{versio}.csv"
    informe = sortida / f"{versio}.informe.json"
    violacions = sortida / f"{versio}.violacions.csv"
    referencia = _exporta_referencia(conn, dades.nom_referencia, sortida)
    exportar(conn, versio, proposta)
    args = [sys.executable, "-m", "horaris", "check", str(proposta), "--paquet", str(arrel)]
    args += ["--json", str(informe), "--violacions", str(violacions)]
    args += _opcions(dades, carpeta_escenari, referencia)
    _esborra_informe_antic(informe)
    codi = _executa(args, dir_verificador, timeout_s)
    veredicte, text_informe = _llegir_veredicte(informe)
    conn.execute(_GUARDAR_RESULTAT, (veredicte, text_informe, dades.id_versio))
    return ResultatVerificacio(codi, veredicte, proposta, informe, violacions)


def _llegir_versio(conn: sqlite3.Connection, versio: str) -> _Versio:
    fila: sqlite3.Row | None = conn.execute(_LLEGIR_VERSIO, (versio,)).fetchone()
    if fila is None:
        raise VerificadorError("la versión de horario no existe")
    id_versio: object = fila[0]
    mode: object = fila[2]
    if not isinstance(id_versio, int) or not isinstance(mode, str):
        raise _format_inesperat()
    nom_referencia = _text_opcional(fila[5])
    if fila[4] is not None and nom_referencia is None:
        raise _format_inesperat()
    return _Versio(
        id_versio=id_versio,
        semestre=_enter_opcional(fila[1]),
        nomes_aules=mode == _MODE_NOMES_AULES,
        id_escenari=_text_opcional(fila[3]),
        nom_referencia=nom_referencia,
    )


def _enter_opcional(valor: object) -> int | None:
    if valor is None or isinstance(valor, int):
        return valor
    raise _format_inesperat()


def _text_opcional(valor: object) -> str | None:
    if valor is None or isinstance(valor, str):
        return valor
    raise _format_inesperat()


def _format_inesperat() -> VerificadorError:
    return VerificadorError("la fila de la versión tiene un formato inesperado")


def _carpeta_escenari(arrel: Path, id_escenari: str) -> Path:
    """Carpeta del escenario dentro del paquete; valida el identificador antes de construir la ruta."""
    if PATRO_ESCENARI.fullmatch(id_escenari) is None:
        raise VerificadorError("identificador de escenario no válido")
    carpeta = (arrel / "escenaris" / id_escenari).resolve()
    if not carpeta.is_relative_to(arrel) or not carpeta.is_dir():
        raise VerificadorError("la carpeta del escenario no existe dentro del paquete")
    return carpeta


def _exporta_referencia(conn: sqlite3.Connection, nom_referencia: str | None, sortida: Path) -> Path | None:
    if nom_referencia is None:
        return None
    validar_nom_versio(nom_referencia)
    referencia = sortida / f"{nom_referencia}.csv"
    exportar(conn, nom_referencia, referencia)
    return referencia


def _opcions(dades: _Versio, carpeta_escenari: Path | None, referencia: Path | None) -> list[str]:
    opcions: list[str] = []
    if dades.semestre is not None:
        opcions += ["--semestre", str(dades.semestre)]
    if dades.nomes_aules:
        opcions.append("--nomes-aules")
    if carpeta_escenari is not None:
        opcions += ["--escenari", str(carpeta_escenari)]
    if referencia is not None:
        opcions += ["--referencia", str(referencia)]
    return opcions


def _esborra_informe_antic(informe: Path) -> None:
    """Evita leer el informe de una ejecución anterior si el verificador no escribe uno nuevo."""
    try:
        informe.unlink(missing_ok=True)
    except OSError as exc:
        raise VerificadorError("no se ha podido preparar la carpeta de salida") from exc


def _executa(args: list[str], dir_verificador: Path, timeout_s: float) -> int:
    """Lanza el verificador y devuelve su código de salida (0 o 1); nunca expone stdout/stderr."""
    try:
        # Seguro: lista de argumentos sin shell, ejecutable = sys.executable y nombres/rutas ya validados.
        proces = subprocess.run(  # noqa: S603  # nosec B603
            args,
            cwd=dir_verificador,
            env={**os.environ, "PYTHONUTF8": "1"},
            shell=False,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificadorError(f"el verificador ha superado el límite de {timeout_s:g} s") from exc
    except OSError as exc:
        raise VerificadorError("no se ha podido lanzar el verificador") from exc
    if proces.returncode not in _CODIS_ESPERATS:
        raise VerificadorError(f"el verificador ha terminado con el código {proces.returncode}")
    return proces.returncode


def _llegir_veredicte(informe: Path) -> tuple[str, str]:
    """Devuelve (veredicte, texto del JSON) validando que el veredicto está en `VEREDICTES`."""
    try:
        text = informe.read_text(encoding="utf-8")
        dada: object = json.loads(text)
    except (OSError, ValueError) as exc:
        raise VerificadorError("el informe JSON del verificador no se puede leer") from exc
    if not isinstance(dada, dict):
        raise VerificadorError("el informe JSON del verificador no es un objeto")
    veredicte: object = dada.get("veredicte")
    if not isinstance(veredicte, str) or veredicte not in VEREDICTES:
        raise VerificadorError("el verificador ha devuelto un veredicto no reconocido")
    return veredicte, text
