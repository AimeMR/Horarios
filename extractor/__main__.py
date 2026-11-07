"""CLI del extractor: `migrate`, `load`, `setup`, `export` y `verificar`.

Códigos de salida: 0 = bien; 1 = `verificar` con veredicto NO VALIDA; 2 = error. Solo imprime recuentos, rutas,
versiones y veredictos, nunca valores de filas del paquete.
"""

import argparse
import math
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from extractor import config
from extractor.db import connect
from extractor.errors import ExtractorError
from extractor.export import exportar, validar_nom_versio
from extractor.load import carregar
from extractor.migrate import baixar, pujar
from extractor.verificador import verificar

CODI_OK = 0
CODI_NO_VALIDA = 1
CODI_ERROR = 2

DIR_SORTIDA = Path("out")
TIMEOUT_DEFECTE_S = 900.0
PREFIX_VALIDA = "VALIDA"
MISSATGE_ERROR_BD = "error de base de datos"

Comanda = Callable[[argparse.Namespace], int]


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de `uv run extractor` y `python -m extractor`; devuelve el código de salida."""
    args = _parser().parse_args(argv)
    nom_comanda: str = args.comanda
    try:
        return _COMANDES[nom_comanda](args)
    except ExtractorError as error:
        return _error(str(error))
    except sqlite3.Error:
        return _error(MISSATGE_ERROR_BD)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="extractor", description="Migraciones, carga y exportación de la BD.")
    parser.add_argument("--db", help=f"fichero SQLite (por defecto, la variable {config.VAR_DB})")
    subparsers = parser.add_subparsers(dest="comanda", required=True, metavar="COMANDA")

    migrate = subparsers.add_parser("migrate", help="aplica las migraciones pendientes o revierte N")
    migrate.add_argument("--down", type=int, metavar="N", help="revierte las N migraciones más recientes")

    for nom, ajuda in (("load", "carga el paquete en la BD"), ("setup", "migrate + load")):
        subparser = subparsers.add_parser(nom, help=ajuda)
        _afegeix_paquet(subparser)
        subparser.add_argument("--reset", action="store_true", help="vacía las tablas antes de cargar")

    export = subparsers.add_parser("export", help="exporta una versión de horario a CSV")
    export.add_argument("--versio", required=True, metavar="NOM")
    export.add_argument("--out", metavar="RUTA", help="por defecto out/<NOM>.csv")

    verificar_parser = subparsers.add_parser("verificar", help="pasa una versión por el verificador oficial")
    verificar_parser.add_argument("--versio", required=True, metavar="NOM")
    _afegeix_paquet(verificar_parser)
    ajuda_verificador = f"carpeta con horaris/ (por defecto, la variable {config.VAR_VERIFICADOR})"
    verificar_parser.add_argument("--verificador", metavar="RUTA", help=ajuda_verificador)
    verificar_parser.add_argument("--out-dir", metavar="RUTA", help="por defecto out/")
    verificar_parser.add_argument("--timeout", type=_segons, default=TIMEOUT_DEFECTE_S, metavar="SEGUNDOS")
    return parser


def _afegeix_paquet(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--paquet", metavar="RUTA", help=f"carpeta del paquete (por defecto, {config.VAR_PAQUET})")


def _segons(text: str) -> float:
    try:
        valor = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("tiene que ser un número de segundos") from exc
    if not math.isfinite(valor) or valor <= 0:
        raise argparse.ArgumentTypeError("tiene que ser un número de segundos mayor que 0")
    return valor


def _connecta(args: argparse.Namespace) -> sqlite3.Connection:
    """Resuelve la ruta de la BD (argumento o HORARIS_DB), crea su carpeta y abre la conexión."""
    valor: str | None = args.db
    ruta = config.ruta_db(valor)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return connect(ruta)


def _paquet(args: argparse.Namespace) -> Path:
    valor: str | None = args.paquet
    return config.ruta_paquet(valor)


def _cmd_migrate(args: argparse.Namespace) -> int:
    down: int | None = args.down
    with closing(_connecta(args)) as conn:
        if down is None:
            _imprimeix_migracions(pujar(conn), "aplicada")
        else:
            _imprimeix_migracions(baixar(conn, down), "revertida")
    return CODI_OK


def _cmd_load(args: argparse.Namespace) -> int:
    paquet = _paquet(args)
    reset: bool = args.reset
    with closing(_connecta(args)) as conn:
        _imprimeix_recomptes(carregar(conn, paquet, reset=reset))
    return CODI_OK


def _cmd_setup(args: argparse.Namespace) -> int:
    paquet = _paquet(args)
    reset: bool = args.reset
    with closing(_connecta(args)) as conn:
        _imprimeix_migracions(pujar(conn), "aplicada")
        _imprimeix_recomptes(carregar(conn, paquet, reset=reset))
    return CODI_OK


def _cmd_export(args: argparse.Namespace) -> int:
    versio = validar_nom_versio(args.versio)
    out: str | None = args.out
    desti = Path(out) if out else DIR_SORTIDA / f"{versio}.csv"
    with closing(_connecta(args)) as conn:
        files = exportar(conn, versio, desti)
    _sortida(f"exportadas {files} filas de la versión {versio} a {desti}")
    return CODI_OK


def _cmd_verificar(args: argparse.Namespace) -> int:
    versio = validar_nom_versio(args.versio)
    paquet = _paquet(args)
    valor_verificador: str | None = args.verificador
    dir_verificador = config.ruta_verificador(valor_verificador, paquet)
    out_dir: str | None = args.out_dir
    dir_sortida = Path(out_dir) if out_dir else DIR_SORTIDA
    timeout_s: float = args.timeout
    with closing(_connecta(args)) as conn:
        resultat = verificar(conn, versio, paquet, dir_verificador, dir_sortida, timeout_s)
    _sortida(f"veredicto: {resultat.veredicte}")
    _sortida(f"propuesta: {resultat.proposta}")
    _sortida(f"informe: {resultat.informe}")
    _sortida(f"violaciones: {resultat.violacions}")
    return CODI_OK if resultat.veredicte.startswith(PREFIX_VALIDA) else CODI_NO_VALIDA


def _imprimeix_migracions(versions: list[int], accio: str) -> None:
    if not versions:
        _sortida("no hay migraciones pendientes")
    for version in versions:
        _sortida(f"migración {version:04d} {accio}")


def _imprimeix_recomptes(recomptes: dict[str, int]) -> None:
    _sortida("filas por tabla:")
    amplada = max(len(taula) for taula in recomptes)
    for taula, files in recomptes.items():
        _sortida(f"  {taula:<{amplada}}  {files:>8}")


def _sortida(linia: str) -> None:
    print(linia, file=sys.stdout)


def _error(missatge: str) -> int:
    print(f"error: {missatge}", file=sys.stderr)
    return CODI_ERROR


_COMANDES: dict[str, Comanda] = {
    "migrate": _cmd_migrate,
    "load": _cmd_load,
    "setup": _cmd_setup,
    "export": _cmd_export,
    "verificar": _cmd_verificar,
}


if __name__ == "__main__":
    sys.exit(main())
