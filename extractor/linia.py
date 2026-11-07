"""Línea de un grupo (misma regla que la propiedad `linia` de `horaris/model.py`) y teoría de un subgrupo."""

from collections.abc import Iterable

_TIPUS_TEORIA = "TE"
_DIGITS_MINIMS = 3


def numero(grup: str) -> str:
    """Número del grupo: lo que va tras la última barra ("PAUL/811" -> "811")."""
    return grup.split("/")[-1]


def linia(tipus: str, grup: str) -> str:
    """TE: quita el último dígito si tiene >= 3 cifras y acaba en 0; resto: quita el último si tiene >= 3 cifras."""
    n = numero(grup)
    if len(n) < _DIGITS_MINIMS:
        return n
    if tipus == _TIPUS_TEORIA and not n.endswith("0"):
        return n
    return n[:-1]


def triar_teoria(linia_subgrup: str, teories: Iterable[str]) -> str | None:
    """Teoría (grupo TE de la misma asignatura) de la línea `linia_subgrup`; `None` si no hay o es ambigua."""
    de_la_linia = [grup for grup in teories if linia(_TIPUS_TEORIA, grup) == linia_subgrup]
    exactes = [grup for grup in de_la_linia if numero(grup) == linia_subgrup]
    if len(exactes) == 1:
        return exactes[0]
    if not exactes and len(de_la_linia) == 1:
        return de_la_linia[0]
    return None
