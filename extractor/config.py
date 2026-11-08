"""Resolución de rutas de configuración.

Prioridad: argumento explícito > variable de entorno. No lee ficheros .env: se usan con
`uv run --env-file .env ...`.
"""

import os
from pathlib import Path

from extractor.errors import ConfigError

VAR_DB = "HORARIS_DB"
VAR_PAQUET = "HORARIS_PAQUET"
VAR_VERIFICADOR = "HORARIS_VERIFICADOR"


def _valor_opcional(valor: str | None, variable: str) -> str | None:
    if valor:
        return valor
    return os.environ.get(variable) or None


def _valor_obligatori(valor: str | None, variable: str) -> str:
    resolt = _valor_opcional(valor, variable)
    if resolt is None:
        raise ConfigError(f"falta la ruta: pasa el argumento o define la variable {variable}")
    return resolt


def _carpeta_existent(ruta: Path, variable: str) -> Path:
    if not ruta.is_dir():
        raise ConfigError(f"la carpeta indicada en {variable} (o por argumento) no existe o no es una carpeta")
    return ruta


def ruta_db(valor: str | None = None) -> Path:
    """Ruta del fichero SQLite (puede no existir todavía)."""
    return Path(_valor_obligatori(valor, VAR_DB))


def ruta_paquet(valor: str | None = None) -> Path:
    """Carpeta del paquete de datos; tiene que existir."""
    return _carpeta_existent(Path(_valor_obligatori(valor, VAR_PAQUET)), VAR_PAQUET)


def ruta_verificador(valor: str | None = None, paquet: Path | None = None) -> Path:
    """Carpeta que contiene `horaris/`; por defecto, la carpeta padre del paquete. Tiene que existir."""
    resolt = _valor_opcional(valor, VAR_VERIFICADOR)
    if resolt is not None:
        ruta = Path(resolt)
    else:
        ruta = (paquet if paquet is not None else ruta_paquet()).parent
    return _carpeta_existent(ruta, VAR_VERIFICADOR)
