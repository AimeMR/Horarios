import pytest

from horaris_solver.domain.filters import (
    parse_cursos,
    parse_titulacions,
    resolve_turn,
    session_matches_cursos,
    session_matches_filters,
    session_matches_titulacions,
    turn_from_cohorts,
)


def test_parse_cursos() -> None:
    assert parse_cursos(None) is None
    assert parse_cursos("1r,2n") == frozenset({"1r", "2n"})


def test_parse_cursos_rejects_unknown() -> None:
    try:
        parse_cursos("5e")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "5e" in str(exc)


def test_parse_cursos_still_raises_on_invalid_and_abuse() -> None:
    with pytest.raises(ValueError, match="5e"):
        parse_cursos("5e")
    with pytest.raises(ValueError):
        parse_cursos("1r,nope")
    with pytest.raises(ValueError):
        parse_cursos("1r;DROP")


def test_session_matches_cursos() -> None:
    cohorts = ("GEI:1r", "GEET:2n")
    assert session_matches_cursos(cohorts, frozenset({"1r"}))
    assert session_matches_cursos(cohorts, frozenset({"3r"})) is False
    assert session_matches_cursos(cohorts, None)


def test_parse_titulacions() -> None:
    assert parse_titulacions(None) is None
    assert parse_titulacions("gei,GEET") == frozenset({"GEI", "GEET"})


def test_session_matches_titulacions() -> None:
    cohorts = ("GEI:1r", "GEET:2n")
    assert session_matches_titulacions(cohorts, frozenset({"GEI"}))
    assert session_matches_titulacions(cohorts, frozenset({"GED"})) is False
    assert session_matches_titulacions(cohorts, None)


def test_session_matches_filters_combined() -> None:
    cohorts = ("GEI:2n",)
    assert session_matches_filters(
        cohorts, cursos=frozenset({"2n"}), titulacions=frozenset({"GEI"})
    )
    assert (
        session_matches_filters(
            cohorts, cursos=frozenset({"2n"}), titulacions=frozenset({"GEET"})
        )
        is False
    )


def test_turn_from_cohorts() -> None:
    assert turn_from_cohorts(("GEI:1r",), "tarda") == "mati"
    assert turn_from_cohorts(("GEI:3r",), "mati") == "tarda"
    assert turn_from_cohorts(("GEI:1r", "GEI:3r"), "mati") == "mati"


def test_resolve_turn_prefers_explicit_group_turn() -> None:
    assert resolve_turn(("GEI:1r",), "tarda") == "tarda"
    assert resolve_turn(("GEI:2n",), "mati") == "mati"
    assert resolve_turn(("GEI:1r",), "desconegut") == "mati"
