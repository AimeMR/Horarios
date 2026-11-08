"""Validación de los valores de una fila CSV, espejo de los CHECK del esquema SQLite.

Cada valor inválido produce `CargaError(fichero, línea, columna, motiu)`; el `motiu` describe la regla y nunca
incluye el valor recibido.
"""

import re
from datetime import date, datetime

from extractor.csvio import FilaCsv
from extractor.errors import CargaError

DIES = frozenset({"L", "M", "X", "J", "V"})
TIPUS_GRUP = frozenset({"TE", "PAUL", "PLAB", "SEM"})
TORNS = frozenset({"mati", "tarda"})
CURSOS = frozenset({"1r", "2n", "3r", "4t", "M", "?"})
ALUMNES_ORIGEN = frozenset({"sigma", "estimat", "sense_dada"})
TIPUS_AULA = frozenset({"Aules docents", "Laboratoris docents", "Seminaris", "Aules informàtiques"})
TIPUS_CALENDARI = frozenset({"festiu", "no_lectiu", "aturada", "avaluacio"})
DC = frozenset({"P", "S"})

_ENTER = re.compile(r"[0-9]{1,18}")
_HORA = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]")
_DATA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATA_DMY = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}")
_SETMANA = re.compile(r"[0-9]{4}-W(?:0[1-9]|[1-4][0-9]|5[0-3])")
_MINUTS_DIA = 24 * 60


class Validador:
    """Valida columnas de las filas de un fichero; los errores llevan el nombre de ese fichero."""

    def __init__(self, fichero: str) -> None:
        self._fichero = fichero

    def text(self, fila: FilaCsv, col: str) -> str:
        valor = self._net(fila, col)
        if not valor:
            raise self._error(fila, col, "campo obligatorio vacío")
        return valor

    def text_opcional(self, fila: FilaCsv, col: str) -> str | None:
        return self._net(fila, col) or None

    def opcio(self, fila: FilaCsv, col: str, permesos: frozenset[str]) -> str:
        valor = self.text(fila, col)
        if valor not in permesos:
            raise self._error(fila, col, "fuera de los valores permitidos")
        return valor

    def opcio_opcional(self, fila: FilaCsv, col: str, permesos: frozenset[str]) -> str | None:
        if not self._net(fila, col):
            return None
        return self.opcio(fila, col, permesos)

    def enter(self, fila: FilaCsv, col: str, minim: int = 0) -> int:
        valor = self._net(fila, col)
        if not _ENTER.fullmatch(valor):
            raise self._error(fila, col, "no es un entero no negativo")
        numero = int(valor)
        if numero < minim:
            raise self._error(fila, col, f"por debajo del mínimo permitido ({minim})")
        return numero

    def enter_opcional(self, fila: FilaCsv, col: str, minim: int = 0) -> int | None:
        if not self._net(fila, col):
            return None
        return self.enter(fila, col, minim)

    def bool01(self, fila: FilaCsv, col: str) -> int:
        valor = self._net(fila, col)
        if valor == "1":
            return 1
        if valor in ("0", ""):
            return 0
        raise self._error(fila, col, "no es 0, 1 ni vacío")

    def hora(self, fila: FilaCsv, col: str) -> str:
        valor = self._net(fila, col)
        if not _HORA.fullmatch(valor):
            raise self._error(fila, col, "no es una hora HH:MM válida")
        return valor

    def hora_opcional(self, fila: FilaCsv, col: str) -> str | None:
        if not self._net(fila, col):
            return None
        return self.hora(fila, col)

    def data_iso(self, fila: FilaCsv, col: str) -> str:
        valor = self._net(fila, col)
        if not _DATA_ISO.fullmatch(valor):
            raise self._error(fila, col, "no es una fecha AAAA-MM-DD")
        try:
            return date.fromisoformat(valor).isoformat()
        except ValueError as error:
            raise self._error(fila, col, "no es una fecha AAAA-MM-DD existente") from error

    def data_dmy(self, fila: FilaCsv, col: str) -> str:
        valor = self._net(fila, col)
        if not _DATA_DMY.fullmatch(valor):
            raise self._error(fila, col, "no es una fecha DD/MM/AAAA")
        try:
            return datetime.strptime(valor, "%d/%m/%Y").date().isoformat()
        except ValueError as error:
            raise self._error(fila, col, "no es una fecha DD/MM/AAAA existente") from error

    def setmana(self, fila: FilaCsv, col: str) -> str:
        valor = self._net(fila, col)
        if not _SETMANA.fullmatch(valor):
            raise self._error(fila, col, "no es una semana AAAA-Www (01-53)")
        return valor

    def llista(self, fila: FilaCsv, col: str, sep: str = "|") -> list[str]:
        parts = (part.strip() for part in self._cru(fila, col).split(sep))
        return [part for part in parts if part]

    def _cru(self, fila: FilaCsv, col: str) -> str:
        try:
            return fila.valors[col]
        except KeyError as error:
            raise self._error(fila, col, "la columna no existe en la fila") from error

    def _net(self, fila: FilaCsv, col: str) -> str:
        return self._cru(fila, col).strip()

    def _error(self, fila: FilaCsv, col: str, motiu: str) -> CargaError:
        return CargaError(self._fichero, fila.linia, col, motiu)


def sumar_minuts(hora: str, minuts: int) -> str:
    """Suma `minuts` a una hora HH:MM ("08:30" + 60 -> "09:30").

    Lanza `ValueError` si `hora` no es HH:MM válida o el resultado sale del mismo día (00:00-23:59).
    """
    if not _HORA.fullmatch(hora):
        raise ValueError("la hora no tiene el formato HH:MM")
    total = int(hora[:2]) * 60 + int(hora[3:]) + minuts
    if not 0 <= total < _MINUTS_DIA:
        raise ValueError("el resultado sale del día")
    return f"{total // 60:02d}:{total % 60:02d}"
