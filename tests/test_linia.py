import pytest

from extractor.linia import linia, numero, triar_teoria


@pytest.mark.parametrize(
    ("grup", "esperat"),
    [
        ("PAUL/811", "811"),
        ("TE/81", "81"),
        ("PLAB/91", "91"),
        ("SEM/1", "1"),
    ],
)
def test_numero_es_el_que_va_despres_de_la_barra(grup: str, esperat: str) -> None:
    assert numero(grup) == esperat


@pytest.mark.parametrize(
    ("tipus", "grup", "esperat"),
    [
        ("TE", "TE/81", "81"),
        ("TE", "TE/310", "31"),
        ("TE", "TE/415", "415"),
        ("PAUL", "PAUL/811", "81"),
        ("PAUL", "PAUL/415", "41"),
        ("PLAB", "PLAB/91", "91"),
        ("SEM", "SEM/1", "1"),
    ],
)
def test_linia_segons_la_regla_del_verificador(tipus: str, grup: str, esperat: str) -> None:
    assert linia(tipus, grup) == esperat


@pytest.mark.parametrize(
    ("tipus", "grup", "esperat"),
    [
        ("TE", "TE/10", "10"),
        ("TE", "TE/100", "10"),
        ("TE", "TE/301", "301"),
        ("PAUL", "PAUL/1", "1"),
        ("PAUL", "PAUL/100", "10"),
    ],
)
def test_linia_als_limits_de_digits(tipus: str, grup: str, esperat: str) -> None:
    assert linia(tipus, grup) == esperat


def test_triar_teoria_escull_la_de_numero_exacte() -> None:
    assert triar_teoria("31", ["TE/31", "TE/310"]) == "TE/31"


def test_triar_teoria_no_depen_de_l_ordre() -> None:
    assert triar_teoria("31", ["TE/310", "TE/31"]) == "TE/31"


def test_triar_teoria_unica_de_la_linia_encara_que_el_numero_no_coincideixi() -> None:
    assert triar_teoria("31", ["TE/310"]) == "TE/310"


def test_triar_teoria_sense_coincidencia_de_linia_retorna_none() -> None:
    assert triar_teoria("41", ["TE/415"]) is None


def test_triar_teoria_amb_teoria_exacta_de_la_mateixa_linia() -> None:
    assert triar_teoria("81", ["TE/81"]) == "TE/81"


def test_triar_teoria_sense_teories_retorna_none() -> None:
    assert triar_teoria("31", []) is None


def test_triar_teoria_ignora_teories_d_altra_linia() -> None:
    # TE/311 es de la línea 311 (no acaba en 0): la única TE de la línea 31 es TE/310.
    assert triar_teoria("31", ["TE/310", "TE/311"]) == "TE/310"


def test_triar_teoria_diverses_candidates_sense_numero_exacte_retorna_none() -> None:
    assert triar_teoria("31", ["TE/310", "TE/310"]) is None


def test_triar_teoria_accepta_un_iterable_qualsevol() -> None:
    teories = (g for g in ["TE/31", "TE/310"])
    assert triar_teoria("31", teories) == "TE/31"


def test_triar_teoria_amb_linia_calculada_per_a_paul_311() -> None:
    assert triar_teoria(linia("PAUL", "PAUL/311"), ["TE/31", "TE/310"]) == "TE/31"


def test_triar_teoria_amb_linia_calculada_per_a_paul_415() -> None:
    assert triar_teoria(linia("PAUL", "PAUL/415"), ["TE/415"]) is None
