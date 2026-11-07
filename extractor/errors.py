"""Jerarquía de errores del extractor.

Los mensajes nunca incluyen valores de celdas del paquete: solo fichero, línea, columna y motivo.
"""


class ExtractorError(Exception):
    """Error base del extractor; la CLI lo traduce en un mensaje sin traza."""


class ConfigError(ExtractorError):
    """Falta una ruta de configuración o no apunta a una carpeta existente."""


class MigracioError(ExtractorError):
    """Una migración es inválida, falta, está duplicada o ha cambiado tras aplicarse."""


class CargaError(ExtractorError):
    """Un CSV del paquete no se puede cargar; indica dónde, nunca el valor de la celda."""

    def __init__(self, fichero: str, linia: int | None, columna: str | None, motiu: str) -> None:
        self.fichero = fichero
        self.linia = linia
        self.columna = columna
        self.motiu = motiu
        super().__init__(self._missatge())

    def _missatge(self) -> str:
        parts = [f"fichero {self.fichero}"]
        if self.linia is not None:
            parts.append(f"línea {self.linia}")
        if self.columna is not None:
            parts.append(f"columna {self.columna}")
        return f"{', '.join(parts)}: {self.motiu}"


class ExportError(ExtractorError):
    """No se puede exportar una versión de horario (p. ej. no existe)."""


class VerificadorError(ExtractorError):
    """El verificador oficial no se puede lanzar o su salida no es válida."""
