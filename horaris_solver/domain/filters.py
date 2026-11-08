"""Shared load filters for semestre / curs."""

from __future__ import annotations

ALLOWED_CURSOS = frozenset({"1r", "2n", "3r", "4t", "M", "?"})
MORNING_CURSOS = frozenset({"1r", "2n"})
AFTERNOON_CURSOS = frozenset({"3r", "4t", "M", "?"})


def parse_cursos(raw: str | None) -> frozenset[str] | None:
    """Parse comma-separated grades. None means no filter."""
    if raw is None or not str(raw).strip():
        return None
    parts = {p.strip() for p in str(raw).split(",") if p.strip()}
    unknown = parts - ALLOWED_CURSOS
    if unknown:
        raise ValueError(f"unknown curs values: {sorted(unknown)}")
    return frozenset(parts)


def cohort_curs(cohort: str) -> str | None:
    if ":" not in cohort:
        return None
    return cohort.split(":", 1)[1]


def session_matches_cursos(cohorts: tuple[str, ...], cursos: frozenset[str] | None) -> bool:
    if cursos is None:
        return True
    for cohort in cohorts:
        grade = cohort_curs(cohort)
        if grade is not None and grade in cursos:
            return True
    return False


def parse_titulacions(raw: str | None) -> frozenset[str] | None:
    if raw is None or not str(raw).strip():
        return None
    return frozenset(p.strip().upper() for p in str(raw).split(",") if p.strip())


def session_matches_titulacions(
    cohorts: tuple[str, ...],
    titulacions: frozenset[str] | None,
) -> bool:
    if titulacions is None:
        return True
    for cohort in cohorts:
        if ":" not in cohort:
            continue
        if cohort.split(":", 1)[0].upper() in titulacions:
            return True
    return False


def session_matches_filters(
    cohorts: tuple[str, ...],
    *,
    cursos: frozenset[str] | None = None,
    titulacions: frozenset[str] | None = None,
) -> bool:
    return session_matches_cursos(cohorts, cursos) and session_matches_titulacions(cohorts, titulacions)


def turn_from_cohorts(cohorts: tuple[str, ...], fallback: str) -> str:
    """1r/2n → mati; 3r/4t/M → tarda. Mixed or unknown keeps fallback."""
    grades = {cohort_curs(c) for c in cohorts}
    grades.discard(None)
    morning = bool(grades & MORNING_CURSOS)
    afternoon = bool(grades & AFTERNOON_CURSOS)
    if morning and not afternoon:
        return "mati"
    if afternoon and not morning:
        return "tarda"
    return fallback if fallback in {"mati", "tarda", "desconegut", "conflicte"} else "desconegut"


def resolve_turn(cohorts: tuple[str, ...], explicit: str) -> str:
    """Use the group turn from the paquet/DB when present; otherwise infer from grade."""
    if explicit in {"mati", "tarda"}:
        return explicit
    return turn_from_cohorts(cohorts, explicit)
