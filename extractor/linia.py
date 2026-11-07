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


def triar_teoria(linia_subgrup: str, teories: Iterable[str], numero_subgrup: str | None = None) -> str | None:
    """Teoría (grupo TE de la misma asignatura) de un subgrupo, con el criterio del verificador (`check.py`).

    1. La TE de la línea cuyo número es exactamente la línea; si no, la única TE de la línea.
    2. Si no hay ninguna TE de la línea: la TE con el mismo número que el subgrupo («/challenge H2»:
       TE/415 y PAUL/415 son el mismo alumnado aunque la línea no lo diga).
    `None` si no hay candidata o es ambigua.
    """
    teories = list(teories)
    de_la_linia = [grup for grup in teories if linia(_TIPUS_TEORIA, grup) == linia_subgrup]
    if de_la_linia:
        return _unica_de_la_linia(linia_subgrup, de_la_linia)
    if numero_subgrup is None:
        return None
    mateix_numero = [grup for grup in teories if numero(grup) == numero_subgrup]
    return mateix_numero[0] if len(mateix_numero) == 1 else None


def _unica_de_la_linia(linia_subgrup: str, de_la_linia: list[str]) -> str | None:
    exactes = [grup for grup in de_la_linia if numero(grup) == linia_subgrup]
    if len(exactes) == 1:
        return exactes[0]
    if not exactes and len(de_la_linia) == 1:
        return de_la_linia[0]
    return None
