"""Tests de extractor/load/catalegs.py (T7a) sobre el paquete falso y sobre copias con celdas inválidas.

Los recuentos vienen de tests/fixtures/paquet_fals/ESPERAT.md. Todo el contenido es inventado.
"""

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from extractor.errors import CargaError
from extractor.load.catalegs import carregar_catalegs
from tests.conftest import afirma_error_carrega, canviar_cella, comptar, consulta

FITXER_NOU = "escenaris/grau-nou-40/sessions_extra.csv"
EXTERNES = ["J/012", "J/102", "J/124", "B3/0021", "QC/1082"]


@pytest.fixture
def carregat(conn: sqlite3.Connection, paquet_fals: Path) -> sqlite3.Connection:
    carregar_catalegs(conn, paquet_fals)
    return conn


def _escenari_json(paquet: Path, carpeta: str) -> dict[str, object]:
    dades: dict[str, object] = json.loads(
        (paquet / "escenaris" / carpeta / "escenari.json").read_text(encoding="utf-8")
    )
    return dades


def _canvia_clau_json(fitxer: Path, clau: str, valor: object) -> None:
    dades: dict[str, object] = json.loads(fitxer.read_text(encoding="utf-8"))
    dades[clau] = valor
    fitxer.write_text(json.dumps(dades, ensure_ascii=False, indent=2), encoding="utf-8")


def _treu_columna(fitxer: Path, columna: str) -> None:
    with fitxer.open(encoding="utf-8-sig", newline="") as lectura:
        files = list(csv.reader(lectura))
    indexo = files[0].index(columna)
    retallades = [[cela for i, cela in enumerate(fila) if i != indexo] for fila in files]
    with fitxer.open("w", encoding="utf-8", newline="") as escriptura:
        csv.writer(escriptura, lineterminator="\n").writerows(retallades)


# --- Recuentos (ESPERAT.md, "Recuentos esperados") -------------------------------------------------------------

RECUENTS = [
    pytest.param("SELECT COUNT(*) FROM facultat", 1, id="facultat"),
    pytest.param("SELECT COUNT(*) FROM aula", 12, id="aula"),
    pytest.param("SELECT COUNT(*) FROM titulacio", 5, id="titulacio"),
    pytest.param("SELECT COUNT(*) FROM pla_estudis", 5, id="pla_estudis"),
    pytest.param("SELECT COUNT(*) FROM pla_titulacio", 6, id="pla_titulacio"),
    pytest.param("SELECT COUNT(*) FROM calendari", 4, id="calendari"),
    pytest.param("SELECT COUNT(*) FROM escenari", 2, id="escenari"),
]


@pytest.mark.parametrize(("sql", "esperat"), RECUENTS)
def test_recuent_de_files_per_taula(carregat: sqlite3.Connection, sql: str, esperat: int) -> None:
    assert comptar(carregat, sql) == esperat


# --- aula ----------------------------------------------------------------------------------------------------


def test_inventari_aula_camps_del_csv(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT edifici, tipus, capacitat, ordinaria FROM aula WHERE codi = ?", ("Q7/7101",)) == [
        ("Q7", "Aules docents", 40, 1)
    ]


def test_inventari_aula_te_facultat_ee_i_externes_no_en_tenen(carregat: sqlite3.Connection) -> None:
    assert comptar(carregat, "SELECT COUNT(*) FROM aula WHERE id_facultat = 'EE'") == 7
    assert comptar(carregat, "SELECT COUNT(*) FROM aula WHERE id_facultat IS NULL") == 5


def test_ordinaria_segueix_el_csv(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT codi FROM aula WHERE ordinaria = 1 ORDER BY codi") == [
        ("Q7/7101",),
        ("Q7/7102",),
        ("Q8/8103",),
    ]


def test_integrat_nomes_al_laboratori_amb_integrat_a_la_descripcio(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT codi FROM aula WHERE integrat = 1") == [("Q7/7204",)]


def test_nomes_plab_nomes_a_la_espina_q5(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT codi FROM aula WHERE nomes_plab = 1") == [("Q5/5105",)]


@pytest.mark.parametrize("codi", EXTERNES)
def test_aula_externa_fixa(carregat: sqlite3.Connection, codi: str) -> None:
    assert consulta(
        carregat,
        "SELECT dins_aulari, admet_noves, tipus, capacitat FROM aula WHERE codi = ?",
        (codi,),
    ) == [(0, 0, None, None)]


def test_integrat_ignora_majuscules(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / "aules.csv", "descripcio", 5, "Laboratori INTEGRAT fictici")
    carregar_catalegs(conn, copia_paquet)
    assert consulta(conn, "SELECT integrat FROM aula WHERE codi = 'Q5/5105'") == [(1,)]


def test_externa_ja_inventariada_no_es_duplica_ni_sobreescriu(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    fitxer = copia_paquet / "aules.csv"
    fitxer.write_text(
        fitxer.read_text(encoding="utf-8") + "J/012,J,Aules docents,Aula fictícia del inventari,20,1\n",
        encoding="utf-8",
    )
    carregar_catalegs(conn, copia_paquet)
    assert comptar(conn, "SELECT COUNT(*) FROM aula") == 12
    assert consulta(conn, "SELECT tipus, dins_aulari FROM aula WHERE codi = 'J/012'") == [("Aules docents", 1)]


def test_tipus_daula_fora_de_la_llista_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / "aules.csv", "tipus", 1, "TIPUS-FALS")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    afirma_error_carrega(error.value, "aules.csv", 2, "tipus", "TIPUS-FALS")


def test_columna_que_falta_a_aules_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _treu_columna(copia_paquet / "aules.csv", "capacitat")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    # Nombrar la columna que falta es correcto (no es un dato del paquete); no hay valor de celda que filtrar.
    afirma_error_carrega(error.value, "aules.csv", 1, "capacitat", "ZZ_VALOR_9")


# --- titulacio -----------------------------------------------------------------------------------------------


def test_nivell_master_nomes_a_la_titulacio_de_curs_m(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT codi, nivell FROM titulacio ORDER BY codi") == [
        ("GFA", "grau"),
        ("GFB", "grau"),
        ("GFC", "grau"),
        ("GNOU", "grau"),
        ("MFA", "master"),
    ]


def test_nom_sense_sufix_de_pla_i_nul_als_planes_compartits(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT codi, nom FROM titulacio ORDER BY codi") == [
        ("GFA", "Grau fictici A"),
        ("GFB", None),
        ("GFC", None),
        ("GNOU", None),
        ("MFA", "Màster fictici A"),
    ]


def test_nom_treu_el_sufix_de_pla_del_pla_dune_sola_titulacio(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / "plans.csv", "descripcio", 3, "Màster fictici A (pla 9003, 5è)")
    carregar_catalegs(conn, copia_paquet)
    assert consulta(conn, "SELECT nom FROM titulacio WHERE codi = 'MFA'") == [("Màster fictici A",)]


def test_titulacio_pertany_a_la_facultat_ee(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT DISTINCT id_facultat FROM titulacio") == [("EE",)]


# --- pla_estudis i pla_titulacio -----------------------------------------------------------------------------


def test_data_extraccio_convertida_a_iso(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT pla, data_extraccio FROM pla_estudis WHERE pla <> 'NOU' ORDER BY pla") == [
        ("9001", "2026-10-30"),
        ("9002", "2026-10-30"),
        ("9003", "2026-11-03"),
        ("9004", "2026-11-03"),
    ]


def test_descripcio_de_plans_csv_es_tal_cual(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT descripcio, fitxer_origen FROM pla_estudis WHERE pla = '9002'") == [
        ("Grau fictici B i C (pla 9002, 1r i 2n)", "extracte-fals-9002.csv")
    ]


def test_pla_nou_ve_de_lescenari_grau_nou(carregat: sqlite3.Connection, paquet_fals: Path) -> None:
    descripcio = _escenari_json(paquet_fals, "grau-nou-40")["descripcio"]
    assert consulta(
        carregat, "SELECT descripcio, fitxer_origen, data_extraccio FROM pla_estudis WHERE pla = 'NOU'"
    ) == [(descripcio, FITXER_NOU, "2026-11-05")]


def test_pla_titulacio_separa_el_plus_i_afegeix_nou(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT pla, titulacio FROM pla_titulacio ORDER BY pla, titulacio") == [
        ("9001", "GFA"),
        ("9002", "GFB"),
        ("9002", "GFC"),
        ("9003", "MFA"),
        ("9004", "GFA"),
        ("NOU", "GNOU"),
    ]


def test_data_extraccio_mal_formada_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / "plans.csv", "data_extraccio", 1, "30-10-2026")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    afirma_error_carrega(error.value, "plans.csv", 2, "data_extraccio", "30-10-2026")


# --- calendari -----------------------------------------------------------------------------------------------


def test_aturada_te_horas(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT data, tipus, h_ini, h_fi FROM calendari WHERE tipus = 'aturada'") == [
        ("2027-01-20", "aturada", "08:00", "14:00")
    ]


def test_resta_de_calendari_no_tenen_horas(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT tipus, h_ini, h_fi FROM calendari WHERE tipus <> 'aturada' ORDER BY data") == [
        ("festiu", None, None),
        ("no_lectiu", None, None),
        ("avaluacio", None, None),
    ]


def test_tipus_de_calendari_fora_de_la_llista_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / "calendari.csv", "tipus", 1, "TIPUS-FALS")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    afirma_error_carrega(error.value, "calendari.csv", 2, "tipus", "TIPUS-FALS")


# --- escenari ------------------------------------------------------------------------------------------------


def test_id_escenari_es_el_nom_de_la_carpeta(carregat: sqlite3.Connection) -> None:
    assert consulta(carregat, "SELECT id_escenari, nom FROM escenari ORDER BY id_escenari") == [
        ("contingencies", "contingencies"),
        ("grau-nou-40", "grau-nou-40"),
    ]


def test_descripcio_de_contingencies_es_la_llista_unida_amb_espais(
    carregat: sqlite3.Connection, paquet_fals: Path
) -> None:
    llista = _escenari_json(paquet_fals, "contingencies")["descripcio"]
    assert isinstance(llista, list)
    esperada = " ".join(str(frase) for frase in llista)
    assert consulta(carregat, "SELECT descripcio FROM escenari WHERE id_escenari = 'contingencies'") == [(esperada,)]


def test_descripcio_de_text_de_grau_nou_es_tal_cual(carregat: sqlite3.Connection, paquet_fals: Path) -> None:
    descripcio = _escenari_json(paquet_fals, "grau-nou-40")["descripcio"]
    assert consulta(carregat, "SELECT descripcio FROM escenari WHERE id_escenari = 'grau-nou-40'") == [(descripcio,)]


@pytest.mark.parametrize(("valor", "esperat"), [(True, 1), (False, 0)])
def test_ficticia_es_0_o_1_segons_el_json(
    copia_paquet: Path, conn: sqlite3.Connection, valor: bool, esperat: int
) -> None:
    _canvia_clau_json(copia_paquet / "escenaris" / "contingencies" / "escenari.json", "ficticia", valor)
    carregar_catalegs(conn, copia_paquet)
    assert consulta(conn, "SELECT ficticia FROM escenari WHERE id_escenari = 'contingencies'") == [(esperat,)]


def test_json_mal_format_falla_sense_linia(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    fitxer = copia_paquet / "escenaris" / "contingencies" / "escenari.json"
    fitxer.write_text('{"nom": "NOM-FALS-7" "ficticia"', encoding="utf-8")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    assert error.value.fichero == "escenaris/contingencies/escenari.json"
    assert error.value.linia is None
    assert "NOM-FALS-7" not in str(error.value)


def test_clau_amb_tipus_incorrecte_falla_amb_la_clau(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _canvia_clau_json(copia_paquet / "escenaris" / "contingencies" / "escenari.json", "ficticia", "VALOR-FALS")
    with pytest.raises(CargaError) as error:
        carregar_catalegs(conn, copia_paquet)
    afirma_error_carrega(error.value, "escenaris/contingencies/escenari.json", None, "ficticia", "VALOR-FALS")
