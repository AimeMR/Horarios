import pytest
from extractor.csvio import FilaCsv
from extractor.validacio import (
    ALUMNES_ORIGEN,
    CURSOS,
    DC,
    DIES,
    TIPUS_AULA,
    TIPUS_CALENDARI,
    TIPUS_GRUP,
    TORNS,
    Validador,
    sumar_minuts,
)

from extractor.errors import CargaError

FICHER = "sessions.csv"
LINIA = 7
COLUMNA = "camp"
VALOR_INVALID = "ZZ_VALOR_9"


def _fila(valor: str, columna: str = COLUMNA) -> FilaCsv:
    return FilaCsv(linia=LINIA, valors={columna: valor})


def _validador() -> Validador:
    return Validador(FICHER)


def _assert_error_de_fila(excinfo: pytest.ExceptionInfo[CargaError], columna: str = COLUMNA) -> None:
    error = excinfo.value
    assert error.fichero == FICHER
    assert error.linia == LINIA
    assert error.columna == columna
    assert VALOR_INVALID not in str(error)


# ---------------------------------------------------------------- constants (espejo dels CHECK)


@pytest.mark.parametrize(
    ("constant", "esperat"),
    [
        pytest.param(DIES, frozenset({"L", "M", "X", "J", "V"}), id="dies"),
        pytest.param(TIPUS_GRUP, frozenset({"TE", "PAUL", "PLAB", "SEM"}), id="tipus_grup"),
        pytest.param(TORNS, frozenset({"mati", "tarda"}), id="torns"),
        pytest.param(CURSOS, frozenset({"1r", "2n", "3r", "4t", "M", "?"}), id="cursos"),
        pytest.param(ALUMNES_ORIGEN, frozenset({"sigma", "estimat", "sense_dada"}), id="alumnes_origen"),
        pytest.param(
            TIPUS_AULA,
            frozenset({"Aules docents", "Laboratoris docents", "Seminaris", "Aules informàtiques"}),
            id="tipus_aula",
        ),
        pytest.param(TIPUS_CALENDARI, frozenset({"festiu", "no_lectiu", "aturada", "avaluacio"}), id="calendari"),
        pytest.param(DC, frozenset({"P", "S"}), id="dc"),
    ],
)
def test_constants_son_els_valors_del_esquema(constant: frozenset[str], esperat: frozenset[str]) -> None:
    assert constant == esperat


# ---------------------------------------------------------------- text


@pytest.mark.parametrize(
    ("valor", "esperat"),
    [("abc", "abc"), ("  abc  ", "abc"), ("Assignatura Falsa 1", "Assignatura Falsa 1")],
)
def test_text_retalla_i_retorna_el_valor(valor: str, esperat: str) -> None:
    assert _validador().text(_fila(valor), COLUMNA) == esperat


@pytest.mark.parametrize("valor", ["", "   "])
def test_text_obligatori_buit_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().text(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


@pytest.mark.parametrize(("valor", "esperat"), [("  ", None), ("", None), ("x ", "x")])
def test_text_opcional_buit_retorna_none(valor: str, esperat: str | None) -> None:
    assert _validador().text_opcional(_fila(valor), COLUMNA) == esperat


# ---------------------------------------------------------------- opcio


def test_opcio_accepta_un_valor_permes() -> None:
    assert _validador().opcio(_fila("L"), COLUMNA, DIES) == "L"


def test_opcio_dia_fora_de_l_v_falla() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().opcio(_fila("S", "dia"), "dia", DIES)
    _assert_error_de_fila(excinfo, columna="dia")


def test_opcio_valor_desconegut_falla_sense_mostrar_el_valor() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().opcio(_fila(VALOR_INVALID), COLUMNA, DIES)
    _assert_error_de_fila(excinfo)


@pytest.mark.parametrize("valor", ["l", ""])
def test_opcio_es_sensible_a_majuscules_i_rebutja_buit(valor: str) -> None:
    with pytest.raises(CargaError):
        _validador().opcio(_fila(valor), COLUMNA, DIES)


def test_opcio_opcional_buit_retorna_none() -> None:
    assert _validador().opcio_opcional(_fila(""), COLUMNA, TORNS) is None


def test_opcio_opcional_valid_retorna_el_valor() -> None:
    assert _validador().opcio_opcional(_fila("tarda"), COLUMNA, TORNS) == "tarda"


def test_opcio_opcional_invalid_falla() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().opcio_opcional(_fila(VALOR_INVALID), COLUMNA, TORNS)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- enter


@pytest.mark.parametrize(("valor", "esperat"), [("0", 0), ("42", 42)])
def test_enter_retorna_el_nombre(valor: str, esperat: int) -> None:
    assert _validador().enter(_fila(valor), COLUMNA) == esperat


def test_enter_minim_inclos() -> None:
    assert _validador().enter(_fila("5"), COLUMNA, minim=5) == 5


def test_enter_per_sota_del_minim_falla() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().enter(_fila("4"), COLUMNA, minim=5)
    _assert_error_de_fila(excinfo)


@pytest.mark.parametrize("valor", ["-1", "3.5", "", VALOR_INVALID])
def test_enter_negatiu_decimal_buit_o_no_numeric_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().enter(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


def test_enter_opcional_buit_retorna_none() -> None:
    assert _validador().enter_opcional(_fila(""), COLUMNA) is None


def test_enter_opcional_valid_retorna_el_nombre() -> None:
    assert _validador().enter_opcional(_fila("7"), COLUMNA) == 7


def test_enter_opcional_negatiu_falla() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().enter_opcional(_fila("-1"), COLUMNA)
    _assert_error_de_fila(excinfo)


def test_enter_opcional_no_numeric_falla_sense_mostrar_el_valor() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().enter_opcional(_fila(VALOR_INVALID), COLUMNA)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- bool01


@pytest.mark.parametrize(("valor", "esperat"), [("1", 1), ("0", 0), ("", 0)])
def test_bool01_accepta_0_1_i_buit_com_a_0(valor: str, esperat: int) -> None:
    assert _validador().bool01(_fila(valor), COLUMNA) == esperat


@pytest.mark.parametrize("valor", ["2", VALOR_INVALID])
def test_bool01_rebutja_altres_valors(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().bool01(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- hora


@pytest.mark.parametrize("valor", ["08:30", "00:00", "23:59"])
def test_hora_valida(valor: str) -> None:
    assert _validador().hora(_fila(valor), COLUMNA) == valor


@pytest.mark.parametrize("valor", ["24:00", "25:00", "8:30", "08:60", "08:3", "", VALOR_INVALID])
def test_hora_invalida_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().hora(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


def test_hora_opcional_buida_retorna_none() -> None:
    assert _validador().hora_opcional(_fila(""), COLUMNA) is None


def test_hora_opcional_valida_retorna_la_hora() -> None:
    assert _validador().hora_opcional(_fila("08:30"), COLUMNA) == "08:30"


def test_hora_opcional_invalida_falla() -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().hora_opcional(_fila("25:00"), COLUMNA)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- data_iso / data_dmy


@pytest.mark.parametrize("valor", ["2026-09-14", "2028-02-29"])
def test_data_iso_valida(valor: str) -> None:
    assert _validador().data_iso(_fila(valor), COLUMNA) == valor


@pytest.mark.parametrize("valor", ["2026-02-30", "2027-02-29", "2026-13-01", "30/10/2026", VALOR_INVALID])
def test_data_iso_invalida_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().data_iso(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


@pytest.mark.parametrize(("valor", "esperat"), [("30/10/2026", "2026-10-30"), ("01/01/2026", "2026-01-01")])
def test_data_dmy_converteix_a_iso(valor: str, esperat: str) -> None:
    assert _validador().data_dmy(_fila(valor), COLUMNA) == esperat


@pytest.mark.parametrize("valor", ["2026-10-30", "31/02/2026", "30/13/2026", VALOR_INVALID])
def test_data_dmy_invalida_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().data_dmy(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- setmana


@pytest.mark.parametrize("valor", ["2026-W01", "2026-W38", "2026-W53"])
def test_setmana_valida(valor: str) -> None:
    assert _validador().setmana(_fila(valor), COLUMNA) == valor


@pytest.mark.parametrize("valor", ["2026-W5", "2026-W00", "2026-W54", "26-W38", VALOR_INVALID])
def test_setmana_invalida_falla(valor: str) -> None:
    with pytest.raises(CargaError) as excinfo:
        _validador().setmana(_fila(valor), COLUMNA)
    _assert_error_de_fila(excinfo)


# ---------------------------------------------------------------- llista


@pytest.mark.parametrize(
    ("valor", "esperat"),
    [
        ("a| b||c", ["a", "b", "c"]),
        ("D903|D904", ["D903", "D904"]),
        ("x", ["x"]),
        ("", []),
        ("   ", []),
    ],
)
def test_llista_separa_retalla_i_descarta_buits(valor: str, esperat: list[str]) -> None:
    assert _validador().llista(_fila(valor), COLUMNA) == esperat


def test_llista_amb_separador_propi() -> None:
    assert _validador().llista(_fila("a;b"), COLUMNA, sep=";") == ["a", "b"]


# ---------------------------------------------------------------- sumar_minuts


@pytest.mark.parametrize(
    ("hora", "minuts", "esperat"),
    [("08:30", 60, "09:30"), ("13:30", 90, "15:00"), ("08:00", 0, "08:00"), ("10:15", 105, "12:00")],
)
def test_sumar_minuts(hora: str, minuts: int, esperat: str) -> None:
    assert sumar_minuts(hora, minuts) == esperat
