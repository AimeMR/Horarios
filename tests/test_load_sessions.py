"""Tests de extractor/load/sessions.py (T7b) sobre el paquete falso, el grado nuevo y copias con celdas inválidas.

Los números vienen de tests/fixtures/paquet_fals/ESPERAT.md. Las cifras "base" son las de ESPERAT menos las filas del
grado nuevo (escenaris/grau-nou-40). Todo el contenido es inventado.
"""

import sqlite3
from pathlib import Path

import pytest

from extractor.errors import CargaError
from extractor.load.catalegs import carregar_catalegs
from extractor.load.sessions import carregar_sessions
from tests.conftest import afirma_error_carrega, canviar_cella, comptar, consulta

SESSIONS = "sessions.csv"
ACTIVITATS = "activitats.csv"
EXTRA = "escenaris/grau-nou-40/sessions_extra.csv"


@pytest.fixture
def base(conn: sqlite3.Connection, paquet_fals: Path) -> sqlite3.Connection:
    carregar_catalegs(conn, paquet_fals)
    carregar_sessions(conn, paquet_fals, SESSIONS, ACTIVITATS, None)
    return conn


@pytest.fixture
def amb_grau_nou(base: sqlite3.Connection, paquet_fals: Path) -> sqlite3.Connection:
    carregar_sessions(base, paquet_fals, EXTRA, None, "grau-nou-40")
    return base


# --- Recuentos (ESPERAT.md) ----------------------------------------------------------------------------------

# Recuentos solo con sessions.csv + activitats.csv (base): ESPERAT menos las filas del grado nuevo.
RECUENTS_BASE = [
    pytest.param("SELECT COUNT(*) FROM assignatura", 6, id="assignatura"),
    pytest.param("SELECT COUNT(*) FROM assignatura_pla", 7, id="assignatura_pla"),
    pytest.param("SELECT COUNT(*) FROM cohort", 5, id="cohort"),
    pytest.param("SELECT COUNT(*) FROM assignatura_cohort", 7, id="assignatura_cohort"),
    pytest.param("SELECT COUNT(*) FROM grup", 13, id="grup"),
    pytest.param("SELECT COUNT(*) FROM profe", 8, id="profe"),
    pytest.param("SELECT COUNT(*) FROM docencia", 13, id="docencia"),
    pytest.param("SELECT COUNT(*) FROM activitat", 13, id="activitat"),
    pytest.param("SELECT COUNT(*) FROM sessio", 28, id="sessio"),
]

# Recuentos tras cargar también el grado nuevo: ESPERAT.md tal cual.
RECUENTS_AMB_GRAU_NOU = [
    pytest.param("SELECT COUNT(*) FROM assignatura", 8, id="assignatura"),
    pytest.param("SELECT COUNT(*) FROM assignatura_pla", 9, id="assignatura_pla"),
    pytest.param("SELECT COUNT(*) FROM cohort", 6, id="cohort"),
    pytest.param("SELECT COUNT(*) FROM assignatura_cohort", 9, id="assignatura_cohort"),
    pytest.param("SELECT COUNT(*) FROM grup", 16, id="grup"),
    pytest.param("SELECT COUNT(*) FROM profe", 10, id="profe"),
    pytest.param("SELECT COUNT(*) FROM docencia", 16, id="docencia"),
    pytest.param("SELECT COUNT(*) FROM activitat", 13, id="activitat"),
    pytest.param("SELECT COUNT(*) FROM sessio", 34, id="sessio"),
]


@pytest.mark.parametrize(("sql", "esperat"), RECUENTS_BASE)
def test_recuent_base_sense_grau_nou(base: sqlite3.Connection, sql: str, esperat: int) -> None:
    assert comptar(base, sql) == esperat


@pytest.mark.parametrize(("sql", "esperat"), RECUENTS_AMB_GRAU_NOU)
def test_recuent_amb_grau_nou(amb_grau_nou: sqlite3.Connection, sql: str, esperat: int) -> None:
    assert comptar(amb_grau_nou, sql) == esperat


# --- assignatura, assignatura_pla, assignatura_cohort, cohort ------------------------------------------------


def test_assignatura_te_codi_nom_i_departament_nul(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT codi, nom, id_departament FROM assignatura WHERE codi = '900001'") == [
        ("900001", "Assignatura Falsa 1", None)
    ]


def test_assignatura_pla_separa_els_plans_amb_barra(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT pla FROM assignatura_pla WHERE codi = '900002' ORDER BY pla") == [
        ("9001",),
        ("9004",),
    ]


def test_assignatura_cohort_separa_les_titulacions_amb_barra(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT id_cohort FROM assignatura_cohort WHERE codi = '900003' ORDER BY id_cohort") == [
        ("GFB:2n",),
        ("GFC:2n",),
    ]


@pytest.mark.parametrize(
    ("id_cohort", "torn_esperat"),
    [
        pytest.param("GFA:1r", "mati", id="1r-mati"),
        pytest.param("GFB:2n", "mati", id="2n-mati"),
        pytest.param("MFA:M", "tarda", id="M-tarda"),
        pytest.param("GFA:?", None, id="interrogant-nul"),
    ],
)
def test_cohort_torn_requerit_segons_el_curs(
    base: sqlite3.Connection, id_cohort: str, torn_esperat: str | None
) -> None:
    assert consulta(base, "SELECT torn_requerit FROM cohort WHERE id_cohort = ?", (id_cohort,)) == [(torn_esperat,)]


@pytest.mark.parametrize(("curs", "torn_esperat"), [("3r", "tarda"), ("4t", "tarda")])
def test_cohort_3r_i_4t_son_de_tarda(
    copia_paquet: Path, conn: sqlite3.Connection, curs: str, torn_esperat: str
) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "titulacions_curs", 21, f"GFA:{curs}")
    canviar_cella(copia_paquet / SESSIONS, "titulacions_curs", 22, f"GFA:{curs}")
    carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    assert consulta(conn, "SELECT torn_requerit FROM cohort WHERE id_cohort = ?", (f"GFA:{curs}",)) == [(torn_esperat,)]


# --- grup ----------------------------------------------------------------------------------------------------


def test_id_grup_es_codi_mes_punt_mig_mes_grup(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT id_grup FROM grup WHERE codi = '900001' ORDER BY id_grup") == [
        ("900001·PAUL/811",),
        ("900001·PAUL/812",),
        ("900001·TE/81",),
    ]


@pytest.mark.parametrize(
    ("id_grup", "numero", "linia"),
    [
        pytest.param("900001·TE/81", "81", "81", id="TE/81"),
        pytest.param("900002·TE/310", "310", "31", id="TE/310"),
        pytest.param("900003·TE/415", "415", "415", id="TE/415"),
        pytest.param("900001·PAUL/811", "811", "81", id="PAUL/811"),
        pytest.param("900003·PAUL/415", "415", "41", id="PAUL/415"),
    ],
)
def test_numero_i_linia_del_grup(base: sqlite3.Connection, id_grup: str, numero: str, linia: str) -> None:
    assert consulta(base, "SELECT numero, linia FROM grup WHERE id_grup = ?", (id_grup,)) == [(numero, linia)]


@pytest.mark.parametrize(
    ("id_grup", "esperat"),
    [
        pytest.param("900001·TE/81", (50, "sigma", 60, 0, None, "mati", "TE"), id="TE-amb-capacitat"),
        pytest.param("900001·PAUL/812", (25, "estimat", None, 0, None, "mati", "PAUL"), id="capacitat-buida"),
        pytest.param("900002·PLAB/311", (0, "sense_dada", 20, 0, "R7: PLAB", "mati", "PLAB"), id="fixat"),
        pytest.param("900004·TE/51", (15, "sigma", None, 1, None, "tarda", "TE"), id="sense-espai-tarda"),
    ],
)
def test_atributs_del_grup(base: sqlite3.Connection, id_grup: str, esperat: tuple[object, ...]) -> None:
    assert consulta(
        base,
        "SELECT alumnes, alumnes_origen, capacitat_grup, sense_espai, fixada_motiu, torn_requerit, tipus "
        "FROM grup WHERE id_grup = ?",
        (id_grup,),
    ) == [esperat]


@pytest.mark.parametrize(
    ("id_grup", "teoria_esperada"),
    [
        pytest.param("900001·PAUL/811", "900001·TE/81", id="PAUL/811"),
        pytest.param("900001·PAUL/812", "900001·TE/81", id="PAUL/812"),
        pytest.param("900002·PAUL/311", "900002·TE/31", id="PAUL/311-exacta"),
        pytest.param("900002·PLAB/311", "900002·TE/31", id="PLAB/311-exacta"),
        pytest.param("900003·PAUL/415", "900003·TE/415", id="PAUL/415-regla-H2"),
        pytest.param("900006·PLAB/61", None, id="PLAB/61-sense-te"),
        pytest.param("900091·PAUL/911", "900091·TE/91", id="grau-nou-PAUL/911"),
        pytest.param("900092·PAUL/921", None, id="grau-nou-PAUL/921-sense-te"),
    ],
)
def test_id_grup_teoria_del_subgrup(
    amb_grau_nou: sqlite3.Connection, id_grup: str, teoria_esperada: str | None
) -> None:
    assert consulta(amb_grau_nou, "SELECT id_grup_teoria FROM grup WHERE id_grup = ?", (id_grup,)) == [
        (teoria_esperada,)
    ]


def test_grup_sense_docent_no_te_docencia(base: sqlite3.Connection) -> None:
    assert comptar(base, "SELECT COUNT(*) FROM docencia WHERE id_grup = '900001·PAUL/812'") == 0


def test_grup_amb_dos_docents_te_dues_files(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT id_profe FROM docencia WHERE id_grup = '900002·TE/31' ORDER BY id_profe") == [
        ("D903",),
        ("D904",),
    ]


def test_docencia_vigent_des_de_el_curs_2026_27(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT DISTINCT vigent_des_de, vigent_fins FROM docencia") == [("2026-09-01", None)]


def test_grup_de_grau_nou_es_sigma_i_sense_espai_zero(amb_grau_nou: sqlite3.Connection) -> None:
    assert consulta(
        amb_grau_nou,
        "SELECT id_grup, alumnes_origen, sense_espai FROM grup WHERE codi IN ('900091', '900092') ORDER BY id_grup",
    ) == [
        ("900091·PAUL/911", "sigma", 0),
        ("900091·TE/91", "sigma", 0),
        ("900092·PAUL/921", "sigma", 0),
    ]


# --- profe ---------------------------------------------------------------------------------------------------


def test_profe_codis_del_paquet_i_del_grau_nou(amb_grau_nou: sqlite3.Connection) -> None:
    assert consulta(amb_grau_nou, "SELECT id_profe FROM profe ORDER BY id_profe") == [
        ("D901",),
        ("D903",),
        ("D904",),
        ("D905",),
        ("D906",),
        ("D907",),
        ("D908",),
        ("D909",),
        ("N901",),
        ("N902",),
    ]


def test_profe_nomes_practiques_es_zero(amb_grau_nou: sqlite3.Connection) -> None:
    assert consulta(amb_grau_nou, "SELECT DISTINCT nomes_practiques FROM profe") == [(0,)]


# --- activitat -----------------------------------------------------------------------------------------------


def test_activitat_mapeig_des_de_activitats_csv(base: sqlite3.Connection) -> None:
    assert consulta(
        base,
        "SELECT activitat_id, id_grup, dia, h_ini, h_fi, setmana_primera, setmana_ultima, n_sessions "
        "FROM activitat WHERE activitat_id = 'A90010'",
    ) == [("A90010", "900004·TE/51", "M", "16:00", "17:30", "2026-W39", "2026-W40", 2)]


# --- sessio --------------------------------------------------------------------------------------------------


def test_sessio_mapeig_de_partida(base: sqlite3.Connection) -> None:
    assert consulta(
        base,
        "SELECT id_grup, activitat_id, setmana, durada_min, data_partida, dia_partida, h_ini_partida "
        "FROM sessio WHERE id_sessio = 'S90011'",
    ) == [("900002·PLAB/311", "A90005", "2027-W05", 120, "2027-02-05", "V", "09:00")]


def test_aula_partida_buida_es_nul(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT id_sessio FROM sessio WHERE aula_partida IS NULL ORDER BY id_sessio") == [
        ("S90021",),
        ("S90022",),
        ("S90025",),
        ("S90026",),
    ]


def test_dc_buit_es_nul(base: sqlite3.Connection) -> None:
    assert consulta(base, "SELECT id_sessio, dc FROM sessio WHERE dc IS NOT NULL ORDER BY id_sessio") == [
        ("S90023", "P"),
        ("S90024", "P"),
        ("S90027", "S"),
        ("S90028", "S"),
    ]


def test_aules_addicionals_es_carregat(base: sqlite3.Connection) -> None:
    assert consulta(
        base, "SELECT id_sessio, aules_addicionals_partida FROM sessio WHERE aules_addicionals_partida IS NOT NULL"
    ) == [("S90020", "Q8/8206")]


@pytest.mark.parametrize(
    ("id_sessio", "semestre_esperat"),
    [
        pytest.param("S90001", 1, id="setembre-semestre-1"),
        pytest.param("S90007", 1, id="gener-semestre-1"),
        pytest.param("S90011", 2, id="febrer-semestre-2"),
    ],
)
def test_semestre_coherent_amb_la_data(base: sqlite3.Connection, id_sessio: str, semestre_esperat: int) -> None:
    assert consulta(base, "SELECT semestre FROM sessio WHERE id_sessio = ?", (id_sessio,)) == [(semestre_esperat,)]


def test_sessions_base_no_tenen_escenari(base: sqlite3.Connection) -> None:
    assert comptar(base, "SELECT COUNT(*) FROM sessio WHERE id_escenari IS NULL") == 28


def test_sessions_del_grau_nou_van_a_lescenari_sense_activitat_ni_aula(amb_grau_nou: sqlite3.Connection) -> None:
    assert consulta(
        amb_grau_nou,
        "SELECT id_sessio, id_escenari, activitat_id, aula_partida, id_grup FROM sessio "
        "WHERE id_escenari = 'grau-nou-40' ORDER BY id_sessio",
    ) == [
        ("N90001", "grau-nou-40", None, None, "900091·PAUL/911"),
        ("N90002", "grau-nou-40", None, None, "900091·PAUL/911"),
        ("N90003", "grau-nou-40", None, None, "900091·TE/91"),
        ("N90004", "grau-nou-40", None, None, "900091·TE/91"),
        ("N90005", "grau-nou-40", None, None, "900092·PAUL/921"),
        ("N90006", "grau-nou-40", None, None, "900092·PAUL/921"),
    ]


def test_claus_foranes_sense_errors_al_final(amb_grau_nou: sqlite3.Connection) -> None:
    assert consulta(amb_grau_nou, "PRAGMA foreign_key_check") == []


# --- Casos inválidos sobre una copia del paquete -------------------------------------------------------------


def test_h_fi_que_no_quadra_amb_durada_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "h_fi", 1, "11:05")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 2, "h_fi", "11:05")


def test_alumnes_diferents_al_mateix_grup_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "alumnes", 2, "999")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 3, "alumnes", "999")


def test_tipus_que_no_quadra_amb_el_prefix_del_grup_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "tipus", 3, "PLAB")
    canviar_cella(copia_paquet / SESSIONS, "tipus", 4, "PLAB")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 4, "tipus", "PLAB")


@pytest.mark.parametrize("columna", ["aula_partida", "aules_addicionals_partida"])
def test_aula_que_no_existeix_a_laula_falla(copia_paquet: Path, conn: sqlite3.Connection, columna: str) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, columna, 1, "ZZ/9999")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 2, columna, "ZZ/9999")


def test_torn_fora_de_mati_o_tarda_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "torn_requerit", 1, "nit-fals")
    canviar_cella(copia_paquet / SESSIONS, "torn_requerit", 2, "nit-fals")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 2, "torn_requerit", "nit-fals")


def test_curs_invalid_a_titulacions_curs_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "titulacions_curs", 21, "GFA:5x")
    canviar_cella(copia_paquet / SESSIONS, "titulacions_curs", 22, "GFA:5x")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 22, "titulacions_curs", "GFA:5x")


def test_dc_fora_de_p_o_s_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    carregar_catalegs(conn, copia_paquet)
    canviar_cella(copia_paquet / SESSIONS, "dc", 1, "DC-FALS")
    with pytest.raises(CargaError) as error:
        carregar_sessions(conn, copia_paquet, SESSIONS, ACTIVITATS, None)
    afirma_error_carrega(error.value, SESSIONS, 2, "dc", "DC-FALS")
