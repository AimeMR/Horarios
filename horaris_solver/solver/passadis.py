"""Corridor key matching the official verifier R6 indicator."""


def passadis(aula: str) -> str:
    """«Q1/1011» → «Q1/1» (espina + planta)."""
    if not aula or "/" not in aula:
        return aula
    edif, _, num = aula.partition("/")
    return f"{edif}/{num[:1]}" if num else edif
