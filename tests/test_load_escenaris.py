"""Tests de extractor/load/escenaris.py y extractor/load/partida.py (T7c) y del orquestador de
extractor/load/__init__.py (T9: carregar, esta_migrada, esta_carregada, buidar).

Todo el contenido es inventado y sale de tests/fixtures/paquet_fals. Los casos inválidos usan copias en tmp_path.
Los recuentos vienen de tests/fixtures/paquet_fals/ESPERAT.md.
"""

import csv
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from extractor.db import connect
from extractor.errors import CargaError, ExtractorError
from extractor.export import exportar
from extractor.load import TAULES_DADES, buidar, carregar, esta_carregada, esta_migrada
from extractor.load.catalegs import carregar_catalegs
from extractor.load.escenaris import carregar_escenaris
from extractor.load.partida import carregar_partida
from extractor.load.sessions import carregar_sessions
from tests.conftest import afirma_error_carrega, canviar_cella, comptar, consulta

SESSIONS = "sessions.csv"
ACTIVITATS = "activitats.csv"
PROPOSTA = "proposta_partida.csv"
CONTINGENCIES = "escenaris/contingencies/escenari.json"
JSON_NOU = "escenaris/grau-nou-40/escenari.json"
FITXER_NOU = "escenaris/grau-nou-40/sessions_extra.csv"

# Recuentos de ESPERAT.md tras la carga completa (26 tablas de datos).
ESPERAT: dict[str, int] = {
    "facultat": 1,
    "departament": 0,
    "aula": 12,
    "titulacio": 5,
    "pla_estudis": 5,
    "pla_titulacio": 6,
    "cohort": 6,
    "assignatura": 8,
    "assignatura_cohort": 9,
    "assignatura_pla": 9,
    "grup": 16,
    "profe": 10,
    "docencia": 16,
    "escenari": 2,
    "indisponibilitat_profe": 0,
    "activitat": 13,
    "sessio": 34,
    "calendari": 4,
    "tancament_aula": 2,
    "cancellacio": 1,
    "canvi_alumnes": 1,
    "versio_horari": 1,
    "assignacio": 28,
    "relaxacio": 0,
    "relaxacio_sessio": 0,
    "registre_canvi": 0,
}


@pytest.fixture
def base(conn: sqlite3.Connection, paquet_fals: Path) -> sqlite3.Connection:
    """Catálogos y sessions.csv ya cargados; sin grado nuevo ni escenarios."""
    carregar_catalegs(conn, paquet_fals)
    carregar_sessions(conn, paquet_fals, SESSIONS, ACTIVITATS, None)
    return conn


@pytest.fixture
def amb_escenaris(base: sqlite3.Connection, paquet_fals: Path) -> sqlite3.Connection:
    carregar_escenaris(base, paquet_fals)
    return base


@pytest.fixture
def buida(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """BD sin migrar: solo existe el fichero."""
    connexio = connect(tmp_path / "buida.db")
    try:
        yield connexio
    finally:
        connexio.close()


def _base_sobre_copia(conn: sqlite3.Connection, copia: Path) -> None:
    """Catálogos y sessions.csv desde una copia; los escenarios se cargan después en cada test."""
    carregar_catalegs(conn, copia)
    carregar_sessions(conn, copia, SESSIONS, ACTIVITATS, None)


def _canvia_escenari(paquet: Path, clau: str, valor: object) -> None:
    """Sustituye una clave de primer nivel del escenari de contingencies (JSON completo, sin tocar el resto)."""
    fitxer = paquet / CONTINGENCIES
    dades: dict[str, object] = json.loads(fitxer.read_text(encoding="utf-8"))
    dades[clau] = valor
    fitxer.write_text(json.dumps(dades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _renombra_sessions_extra(paquet: Path, nom: str) -> None:
    """Renombra el CSV del grado nuevo y lo declara con ese nombre en la clave `sessions_extra` de su JSON."""
    (paquet / FITXER_NOU).rename(paquet / FITXER_NOU.replace("sessions_extra.csv", nom))
    fitxer = paquet / JSON_NOU
    dades: dict[str, object] = json.loads(fitxer.read_text(encoding="utf-8"))
    dades["sessions_extra"] = nom
    fitxer.write_text(json.dumps(dades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copia_extra_no_declarat(paquet: Path) -> None:
    """Pone un `sessions_extra.csv` (titulación GZZZ) en contingencies, cuyo JSON no tiene la clave."""
    desti = paquet / "escenaris" / "contingencies" / "sessions_extra.csv"
    desti.write_bytes((paquet / FITXER_NOU).read_bytes().replace(b"GNOU", b"GZZZ"))


def _afegeix_columna_data(fitxer: Path, data_primera: str) -> None:
    """Añade la columna `data` a la proposta: solo la primera fila (S90001) tiene valor."""
    with fitxer.open(encoding="utf-8-sig", newline="") as lectura:
        files = list(csv.reader(lectura))
    files[0].append("data")
    for indice, fila in enumerate(files[1:]):
        fila.append(data_primera if indice == 0 else "")
    with fitxer.open("w", encoding="utf-8", newline="") as escriptura:
        csv.writer(escriptura, lineterminator="\n").writerows(files)


def _recomptes(conn: sqlite3.Connection) -> dict[str, int]:
    """Filas de cada tabla de TAULES_DADES. Los nombres salen de la constante del módulo, nunca de datos."""
    return {taula: comptar(conn, f"SELECT COUNT(*) FROM {taula}") for taula in TAULES_DADES}  # noqa: S608


# --- carregar_escenaris: sesiones del grado nuevo ------------------------------------------------------------


RECUENTS_ESCENARIS = [
    pytest.param("SELECT COUNT(*) FROM sessio", 34, id="sessio"),
    pytest.param("SELECT COUNT(*) FROM grup", 16, id="grup"),
    pytest.param("SELECT COUNT(*) FROM escenari", 2, id="escenari"),
    pytest.param("SELECT COUNT(*) FROM tancament_aula", 2, id="tancament_aula"),
    pytest.param("SELECT COUNT(*) FROM cancellacio", 1, id="cancellacio"),
    pytest.param("SELECT COUNT(*) FROM canvi_alumnes", 1, id="canvi_alumnes"),
    pytest.param("SELECT COUNT(*) FROM versio_horari", 0, id="versio_horari"),
]


@pytest.mark.parametrize(("sql", "esperat"), RECUENTS_ESCENARIS)
def test_recuent_despres_de_carregar_escenaris(amb_escenaris: sqlite3.Connection, sql: str, esperat: int) -> None:
    assert comptar(amb_escenaris, sql) == esperat


def test_abans_de_carregar_escenaris_no_hi_ha_sessions_del_grau_nou(base: sqlite3.Connection) -> None:
    assert comptar(base, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", ("grau-nou-40",)) == 0


def test_sessions_del_grau_nou_tenen_id_escenari_grau_nou_40(amb_escenaris: sqlite3.Connection) -> None:
    assert consulta(
        amb_escenaris, "SELECT id_sessio FROM sessio WHERE id_escenari = ? ORDER BY id_sessio", ("grau-nou-40",)
    ) == [
        ("N90001",),
        ("N90002",),
        ("N90003",),
        ("N90004",),
        ("N90005",),
        ("N90006",),
    ]


def test_sessions_base_no_tenen_escenari(amb_escenaris: sqlite3.Connection) -> None:
    assert comptar(amb_escenaris, "SELECT COUNT(*) FROM sessio WHERE id_escenari IS NULL") == 28


def test_escenari_sense_sessions_extra_no_carrega_sessions(amb_escenaris: sqlite3.Connection) -> None:
    assert comptar(amb_escenaris, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", ("contingencies",)) == 0


def test_sessions_extra_amb_un_altre_nom_es_carrega_igual(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _renombra_sessions_extra(copia_paquet, "extra.csv")
    assert carregar(conn, copia_paquet) == ESPERAT
    assert comptar(conn, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", ("grau-nou-40",)) == 6


def test_sessions_extra_no_declarat_al_json_signora(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _copia_extra_no_declarat(copia_paquet)
    assert carregar(conn, copia_paquet) == ESPERAT
    assert comptar(conn, "SELECT COUNT(*) FROM titulacio WHERE codi = ?", ("GZZZ",)) == 0
    assert comptar(conn, "SELECT COUNT(*) FROM cohort WHERE titulacio = ?", ("GZZZ",)) == 0
    assert comptar(conn, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", ("contingencies",)) == 0


def test_carregar_escenaris_no_obre_ni_tanca_la_transaccio(base: sqlite3.Connection, paquet_fals: Path) -> None:
    base.execute("BEGIN")
    carregar_escenaris(base, paquet_fals)
    assert base.in_transaction
    base.execute("ROLLBACK")
    assert comptar(base, "SELECT COUNT(*) FROM tancament_aula") == 0
    assert comptar(base, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", ("grau-nou-40",)) == 0


# --- carregar_escenaris: aulas cerradas, cancelaciones y cambios de alumnos -----------------------------------


def test_tancament_aula_guarda_aula_i_dates(amb_escenaris: sqlite3.Connection) -> None:
    assert consulta(
        amb_escenaris,
        "SELECT id_escenari, aula, data_ini, data_fi FROM tancament_aula ORDER BY aula",
    ) == [
        ("contingencies", "Q7/7101", "2026-09-16", "2026-09-16"),
        ("contingencies", "Q8/8103", "2027-01-11", "2027-01-18"),
    ]


def test_tancament_aula_sense_hores_ni_motiu(amb_escenaris: sqlite3.Connection) -> None:
    assert consulta(amb_escenaris, "SELECT h_ini, h_fi, motiu FROM tancament_aula ORDER BY aula") == [
        (None, None, None),
        (None, None, None),
    ]


def test_cancellacio_guarda_sessio_i_data_de_recuperacio(amb_escenaris: sqlite3.Connection) -> None:
    assert consulta(amb_escenaris, "SELECT id_escenari, id_sessio, recuperar_fins FROM cancellacio") == [
        ("contingencies", "S90014", "2026-10-30"),
    ]


def test_canvi_alumnes_usa_id_grup_i_el_numero_del_json(amb_escenaris: sqlite3.Connection) -> None:
    assert consulta(amb_escenaris, "SELECT id_escenari, id_grup, alumnes FROM canvi_alumnes") == [
        ("contingencies", "900001·TE/81", 70),
    ]


def test_canvi_alumnes_admet_zero_alumnes(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _base_sobre_copia(conn, copia_paquet)
    _canvia_escenari(copia_paquet, "alumnes", [{"codi": "900001", "grup": "TE/81", "alumnes": 0}])
    carregar_escenaris(conn, copia_paquet)
    assert consulta(conn, "SELECT alumnes FROM canvi_alumnes") == [(0,)]


# --- carregar_escenaris: entradas inválidas (CargaError sin el valor) -----------------------------------------


INVALIDS_ESCENARI = [
    pytest.param(
        "aules_tancades",
        [{"aula": "Q9/9999", "data_ini": "2027-01-11", "data_fi": "2027-01-18"}],
        "Q9/9999",
        id="aula-tancada-inexistent",
    ),
    pytest.param(
        "cancellades",
        [{"id_sessio": "S99999", "recuperar_fins": "2026-10-30"}],
        "S99999",
        id="sessio-cancelada-inexistent",
    ),
    pytest.param(
        "alumnes",
        [{"codi": "900099", "grup": "TE/99", "alumnes": 70}],
        "900099",
        id="grup-de-alumnes-inexistent",
    ),
    pytest.param(
        "alumnes",
        [{"codi": "900001", "grup": "TE/81", "alumnes": "setanta"}],
        "setanta",
        id="alumnes-no-numeric",
    ),
]


@pytest.mark.parametrize(("clau", "valor", "valor_prohibit"), INVALIDS_ESCENARI)
def test_escenari_amb_referencia_invalida_falla(
    copia_paquet: Path, conn: sqlite3.Connection, clau: str, valor: object, valor_prohibit: str
) -> None:
    _base_sobre_copia(conn, copia_paquet)
    _canvia_escenari(copia_paquet, clau, valor)
    with pytest.raises(CargaError) as error:
        carregar_escenaris(conn, copia_paquet)
    afirma_error_carrega(error.value, CONTINGENCIES, None, clau, valor_prohibit)


# --- carregar_partida ----------------------------------------------------------------------------------------


ASSIGNACIONS = [
    pytest.param("S90001", "X", "10:00", "Q7/7101", id="aula-del-paquet"),
    pytest.param("S90005", "L", "08:30", "Q8/8103", id="aula-d-una-altra-sessio"),
    pytest.param("S90017", "X", "12:00", "J/012", id="aula-externa"),
    pytest.param("S90020", "J", "12:00", "Q8/8103", id="sessio-amb-aules-addicionals"),
]


def test_carregar_partida_retorna_lid_de_la_versio(base: sqlite3.Connection, paquet_fals: Path) -> None:
    id_versio = carregar_partida(base, paquet_fals)
    assert isinstance(id_versio, int)
    assert consulta(base, "SELECT id_versio FROM versio_horari WHERE nom = ?", ("partida",)) == [(id_versio,)]


def test_versio_partida_es_complet_i_sense_semestre_ni_escenari(base: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar_partida(base, paquet_fals)
    assert consulta(base, "SELECT nom, mode, semestre, id_escenari FROM versio_horari") == [
        ("partida", "complet", None, None),
    ]


def test_assignacio_te_una_fila_per_fila_de_la_proposta(base: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar_partida(base, paquet_fals)
    assert comptar(base, "SELECT COUNT(*) FROM assignacio") == 28


@pytest.mark.parametrize(("id_sessio", "dia", "h_ini", "aula"), ASSIGNACIONS)
def test_assignacio_copia_dia_hora_i_aula(
    base: sqlite3.Connection, paquet_fals: Path, id_sessio: str, dia: str, h_ini: str, aula: str
) -> None:
    carregar_partida(base, paquet_fals)
    assert consulta(base, "SELECT id_sessio, dia, h_ini, aula FROM assignacio WHERE id_sessio = ?", (id_sessio,)) == [
        (id_sessio, dia, h_ini, aula),
    ]


def test_aula_buida_de_la_proposta_es_null(base: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar_partida(base, paquet_fals)
    assert consulta(base, "SELECT id_sessio FROM assignacio WHERE aula IS NULL ORDER BY id_sessio") == [
        ("S90021",),
        ("S90022",),
        ("S90025",),
        ("S90026",),
    ]


def test_data_es_null_si_la_proposta_no_te_columna_data(base: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar_partida(base, paquet_fals)
    assert comptar(base, "SELECT COUNT(*) FROM assignacio WHERE data IS NULL") == 28


def test_data_de_la_proposta_es_guarda_si_hi_es(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _base_sobre_copia(conn, copia_paquet)
    _afegeix_columna_data(copia_paquet / PROPOSTA, "2026-09-16")
    carregar_partida(conn, copia_paquet)
    assert consulta(conn, "SELECT id_sessio, data FROM assignacio WHERE data IS NOT NULL") == [
        ("S90001", "2026-09-16"),
    ]


def test_proposta_amb_aula_inexistent_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _base_sobre_copia(conn, copia_paquet)
    canviar_cella(copia_paquet / PROPOSTA, "aula", 1, "Q9/9999")
    with pytest.raises(CargaError) as error:
        carregar_partida(conn, copia_paquet)
    afirma_error_carrega(error.value, PROPOSTA, 2, "aula", "Q9/9999")


def test_proposta_amb_sessio_inexistent_falla(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    _base_sobre_copia(conn, copia_paquet)
    canviar_cella(copia_paquet / PROPOSTA, "id_sessio", 1, "S99999")
    with pytest.raises(CargaError) as error:
        carregar_partida(conn, copia_paquet)
    afirma_error_carrega(error.value, PROPOSTA, 2, "id_sessio", "S99999")


def test_exportar_la_partida_es_byte_a_byte_la_proposta(
    base: sqlite3.Connection, paquet_fals: Path, tmp_path: Path
) -> None:
    carregar_partida(base, paquet_fals)
    desti = tmp_path / "sortida" / "partida.csv"
    assert exportar(base, "partida", desti) == 28
    assert desti.read_bytes() == (paquet_fals / PROPOSTA).read_bytes()


# --- Orquestador carregar (extractor/load/__init__.py, T9) ---------------------------------------------------


def test_esta_migrada_es_cert_despres_de_pujar(conn: sqlite3.Connection) -> None:
    assert esta_migrada(conn)


def test_esta_migrada_es_fals_en_una_bd_sense_migrar(buida: sqlite3.Connection) -> None:
    assert not esta_migrada(buida)


def test_esta_carregada_es_fals_despres_de_migrar(conn: sqlite3.Connection) -> None:
    assert not esta_carregada(conn)


def test_esta_carregada_es_cert_despres_de_carregar(conn: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar(conn, paquet_fals)
    assert esta_carregada(conn)


def test_taules_dades_son_les_taules_del_esquema_sense_schema_migrations(conn: sqlite3.Connection) -> None:
    noms = consulta(
        conn,
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name <> ?",
        ("schema_migrations",),
    )
    assert {nom for (nom,) in noms} == set(TAULES_DADES)
    assert len(TAULES_DADES) == 26


def test_carregar_retorna_els_recomptes_de_cada_taula(conn: sqlite3.Connection, paquet_fals: Path) -> None:
    assert carregar(conn, paquet_fals) == ESPERAT


def test_carregar_sense_migrar_falla_i_indica_migrate(buida: sqlite3.Connection, paquet_fals: Path) -> None:
    with pytest.raises(ExtractorError) as error:
        carregar(buida, paquet_fals)
    assert "migr" in str(error.value)


def test_carregar_sense_reset_si_ja_hi_ha_dades_falla_sense_tocar_res(
    conn: sqlite3.Connection, paquet_fals: Path
) -> None:
    carregar(conn, paquet_fals)
    abans = _recomptes(conn)
    with pytest.raises(ExtractorError) as error:
        carregar(conn, paquet_fals)
    assert "reset" in str(error.value)
    assert _recomptes(conn) == abans


def test_carregar_amb_reset_recarrega_sense_duplicar(conn: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar(conn, paquet_fals)
    assert carregar(conn, paquet_fals, reset=True) == ESPERAT
    assert _recomptes(conn) == ESPERAT


def _afegeix_dades_del_solver(conn: sqlite3.Connection, id_partida: int) -> None:
    """Una versión nueva con referencia a la partida, una asignación, una relajación y un registro de cambio."""
    id_nova = conn.execute(
        "INSERT INTO versio_horari (nom, id_versio_referencia) VALUES (?, ?)", ("solver-fals", id_partida)
    ).lastrowid
    conn.execute(
        "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula) VALUES (?, ?, ?, ?, ?)",
        (id_nova, "S90001", "X", "10:00", "Q7/7102"),
    )
    id_relaxacio = conn.execute(
        "INSERT INTO relaxacio (id_versio, restriccio, justificacio) VALUES (?, ?, ?)",
        (id_nova, "R8-RESERVA", "Justificació falsa"),
    ).lastrowid
    conn.execute("INSERT INTO relaxacio_sessio (id_relaxacio, id_sessio) VALUES (?, ?)", (id_relaxacio, "S90001"))
    conn.execute(
        "INSERT INTO registre_canvi (id_versio_origen, id_versio_desti, id_sessio, de_aula, a_aula, motiu, afectats, "
        "data_avis) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (id_partida, id_nova, "S90001", "Q7/7101", "Q7/7102", "Motiu fals", "Afectats falsos", "2026-11-07"),
    )


def test_reset_buida_tambe_les_taules_que_escriu_el_solver(conn: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar(conn, paquet_fals)
    id_partida = consulta(conn, "SELECT id_versio FROM versio_horari WHERE nom = ?", ("partida",))[0][0]
    assert isinstance(id_partida, int)
    _afegeix_dades_del_solver(conn, id_partida)
    assert comptar(conn, "SELECT COUNT(*) FROM registre_canvi") == 1
    assert carregar(conn, paquet_fals, reset=True) == ESPERAT
    assert consulta(conn, "SELECT nom, id_versio_referencia FROM versio_horari") == [("partida", None)]
    for taula in ("relaxacio", "relaxacio_sessio", "registre_canvi"):
        assert comptar(conn, f"SELECT COUNT(*) FROM {taula}") == 0, taula  # noqa: S608
    assert comptar(conn, "SELECT COUNT(*) FROM assignacio WHERE aula = ? AND id_sessio = ?", ("Q7/7102", "S90001")) == 0


def test_paquet_amb_error_no_deixa_cap_fila_a_mig(copia_paquet: Path, conn: sqlite3.Connection) -> None:
    canviar_cella(copia_paquet / SESSIONS, "h_fi", 1, "11:05")
    with pytest.raises(CargaError) as error:
        carregar(conn, copia_paquet)
    afirma_error_carrega(error.value, SESSIONS, 2, "h_fi", "11:05")
    assert _recomptes(conn) == {taula: 0 for taula in TAULES_DADES}
    assert not conn.in_transaction


def test_reset_amb_error_conserva_les_dades_anteriors(
    copia_paquet: Path, conn: sqlite3.Connection, paquet_fals: Path
) -> None:
    carregar(conn, paquet_fals)
    canviar_cella(copia_paquet / SESSIONS, "h_fi", 1, "11:05")
    with pytest.raises(CargaError):
        carregar(conn, copia_paquet, reset=True)
    assert _recomptes(conn) == ESPERAT
    assert esta_carregada(conn)


def test_buidar_deixa_les_taules_buides_i_conserva_lesquema(conn: sqlite3.Connection, paquet_fals: Path) -> None:
    carregar(conn, paquet_fals)
    buidar(conn)
    assert _recomptes(conn) == {taula: 0 for taula in TAULES_DADES}
    assert esta_migrada(conn)
    assert not esta_carregada(conn)
