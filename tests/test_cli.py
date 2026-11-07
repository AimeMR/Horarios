"""Tests de la CLI extractor/__main__.py (T9) llamando a `main([...])` directamente.

La BD va en tmp_path y el paquet es tests/fixtures/paquet_fals (inventado). El verificador es el falso de
tests/fixtures/verificador_fals; su comportamiento lo elige HORARIS_FALS_MODE. Los recuentos vienen de
tests/fixtures/paquet_fals/ESPERAT.md. Códigos de salida: 0 bien, 1 verificar NO VALIDA, 2 error.
"""

import re
from contextlib import closing
from pathlib import Path

import pytest
from extractor.__main__ import main

from extractor.db import connect
from tests.conftest import comptar, consulta

VAR_DB = "HORARIS_DB"
VAR_PAQUET = "HORARIS_PAQUET"
VAR_VERIFICADOR = "HORARIS_VERIFICADOR"
VAR_MODE = "HORARIS_FALS_MODE"

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAQUET_FALS = FIXTURES / "paquet_fals"
VERIFICADOR_FALS = FIXTURES / "verificador_fals"
PROPOSTA_FIXTURE = PAQUET_FALS / "proposta_partida.csv"
MARCADOR_FALS = "DADA-FALSA-9001"  # el falso lo escribe en stderr en modo error; la CLI no debe mostrarlo

# Recuentos de ESPERAT.md tras la carga completa.
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


@pytest.fixture(autouse=True)
def _entorn_aillat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sin variables de entorno del usuario y con el directorio actual dentro de tmp_path."""
    for variable in (VAR_DB, VAR_PAQUET, VAR_VERIFICADOR, VAR_MODE):
        monkeypatch.delenv(variable, raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Ruta de la BD; la carpeta padre no existe y la CLI tiene que crearla."""
    return tmp_path / "bd" / "horaris.db"


@pytest.fixture
def carregada(db: Path) -> Path:
    """BD creada con `setup` sobre el paquet falso."""
    assert main(["--db", str(db), "setup", "--paquet", str(PAQUET_FALS)]) == 0
    return db


def _cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Ejecuta `main` y devuelve (código, stdout, stderr). Un SystemExit de argparse cuenta como código de salida."""
    capsys.readouterr()
    try:
        codi = main(argv)
    except SystemExit as sortida:
        assert isinstance(sortida.code, int)
        codi = sortida.code
    captura = capsys.readouterr()
    return codi, captura.out, captura.err


def _recomptes(db: Path) -> dict[str, int]:
    """Filas de cada tabla de ESPERAT. Los nombres salen de la constante del módulo, nunca de datos."""
    with closing(connect(db)) as conn:
        return {taula: comptar(conn, f"SELECT COUNT(*) FROM {taula}") for taula in ESPERAT}  # noqa: S608


def _verificar_argv(db: Path, paquet: Path, sortida: Path) -> list[str]:
    return [
        "--db",
        str(db),
        "verificar",
        "--versio",
        "partida",
        "--paquet",
        str(paquet),
        "--verificador",
        str(VERIFICADOR_FALS),
        "--out-dir",
        str(sortida),
    ]


# --- setup y load --------------------------------------------------------------------------------------------


def test_setup_carrega_la_bd_com_indica_esperat(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codi, _, _ = _cli(["--db", str(db), "setup", "--paquet", str(PAQUET_FALS)], capsys)
    assert codi == 0
    assert _recomptes(db) == ESPERAT


def test_setup_mostra_el_recompte_de_cada_taula_i_no_los_valores(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codi, out, _ = _cli(["--db", str(db), "setup", "--paquet", str(PAQUET_FALS)], capsys)
    assert codi == 0
    for taula, esperat in ESPERAT.items():
        assert re.search(rf"\b{taula}\b.*\b{esperat}\b", out), taula
    assert "Assignatura Falsa" not in out
    assert "Q7/7101" not in out


def test_setup_amb_variables_denvironment(
    db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_DB, str(db))
    monkeypatch.setenv(VAR_PAQUET, str(PAQUET_FALS))
    codi, _, _ = _cli(["setup"], capsys)
    assert codi == 0
    assert _recomptes(db) == ESPERAT


def test_horaris_db_per_variable_es_com_el_flag(
    db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_DB, str(db))
    assert _cli(["migrate"], capsys)[0] == 0
    assert db.is_file()
    assert _cli(["load", "--paquet", str(PAQUET_FALS)], capsys)[0] == 0
    assert _recomptes(db) == ESPERAT


def test_load_sense_reset_si_ja_carregada_falla_i_no_canvia_res(
    carregada: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    abans = _recomptes(carregada)
    codi, _, err = _cli(["--db", str(carregada), "load", "--paquet", str(PAQUET_FALS)], capsys)
    assert codi == 2
    assert "--reset" in err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert _recomptes(carregada) == abans == ESPERAT


def test_load_amb_reset_torna_a_carregar_amb_els_mateixos_recomptes(
    carregada: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codi, _, _ = _cli(["--db", str(carregada), "load", "--paquet", str(PAQUET_FALS), "--reset"], capsys)
    assert codi == 0
    assert _recomptes(carregada) == ESPERAT


def test_load_sobre_bd_sense_migrar_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sense_migrar = tmp_path / "sense_migrar.db"
    with closing(connect(sense_migrar)):
        pass
    codi, _, err = _cli(["--db", str(sense_migrar), "load", "--paquet", str(PAQUET_FALS)], capsys)
    assert codi == 2
    assert "migr" in err
    assert err.startswith("error:")


def test_setup_amb_paquet_inexistent_falla(db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codi, _, err = _cli(["--db", str(db), "setup", "--paquet", str(tmp_path / "no_existeix")], capsys)
    assert codi == 2
    assert err.startswith("error:")
    assert "Traceback" not in err


def test_sense_paquet_ni_variable_nomena_horaris_paquet(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli(["--db", str(db), "migrate"], capsys)[0] == 0
    codi, _, err = _cli(["--db", str(db), "load"], capsys)
    assert codi == 2
    assert "HORARIS_PAQUET" in err
    assert err.startswith("error:")


def test_sense_db_ni_variable_nomena_horaris_db(capsys: pytest.CaptureFixture[str]) -> None:
    codi, _, err = _cli(["migrate"], capsys)
    assert codi == 2
    assert "HORARIS_DB" in err
    assert err.startswith("error:")


# --- migrate -------------------------------------------------------------------------------------------------


def test_migrate_imprimeix_la_versio_1(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codi, out, _ = _cli(["--db", str(db), "migrate"], capsys)
    assert codi == 0
    sense_ruta = out.replace(str(db), "")
    assert re.search(r"(?<!\d)0*1(?!\d)", sense_ruta)


def test_migrate_crea_la_carpeta_de_la_bd(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    desti = tmp_path / "a" / "b" / "bd.db"
    assert _cli(["--db", str(desti), "migrate"], capsys)[0] == 0
    assert desti.is_file()


def test_migrate_down_1_esborra_les_taules_de_dades(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli(["--db", str(db), "migrate"], capsys)[0] == 0
    assert _cli(["--db", str(db), "migrate", "--down", "1"], capsys)[0] == 0
    with closing(connect(db)) as conn:
        taules = consulta(
            conn,
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name <> ?",
            ("schema_migrations",),
        )
    assert taules == []


def test_migrate_repetit_i_despres_de_revertir_tambe_es_0(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli(["--db", str(db), "migrate"], capsys)[0] == 0
    assert _cli(["--db", str(db), "migrate"], capsys)[0] == 0
    assert _cli(["--db", str(db), "migrate", "--down", "1"], capsys)[0] == 0
    assert _cli(["--db", str(db), "migrate"], capsys)[0] == 0


# --- export --------------------------------------------------------------------------------------------------


def test_export_amb_out_escriu_la_fixture_byte_a_byte(
    carregada: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    desti = tmp_path / "sortida" / "p.csv"
    codi, _, _ = _cli(["--db", str(carregada), "export", "--versio", "partida", "--out", str(desti)], capsys)
    assert codi == 0
    assert desti.read_bytes() == PROPOSTA_FIXTURE.read_bytes()


def test_export_sense_out_escriu_a_out_del_directori_actual(
    carregada: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codi, _, _ = _cli(["--db", str(carregada), "export", "--versio", "partida"], capsys)
    assert codi == 0
    assert (Path.cwd() / "out" / "partida.csv").read_bytes() == PROPOSTA_FIXTURE.read_bytes()


def test_export_versio_inexistent_falla_i_no_escriu(
    carregada: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    desti = tmp_path / "no.csv"
    codi, _, err = _cli(["--db", str(carregada), "export", "--versio", "no_existeix", "--out", str(desti)], capsys)
    assert codi == 2
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert not desti.exists()


@pytest.mark.parametrize(
    "versio", ["../x", "a/b", "nom espai", "", "x" * 65], ids=["recorregut", "barra", "espai", "buit", "llarg"]
)
def test_export_nom_de_versio_no_valid_surt_2_i_no_crea_res(
    carregada: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], versio: str
) -> None:
    codi, _, err = _cli(["--db", str(carregada), "export", "--versio", versio], capsys)
    assert codi == 2
    assert err.startswith("error:")
    assert list(tmp_path.rglob("*.csv")) == []
    assert not (Path.cwd() / "out").exists()


# --- verificar (verificador falso) ---------------------------------------------------------------------------


@pytest.mark.parametrize(("mode", "codi_esperat"), [("valida", 0), ("no_valida", 1), ("error", 2)])
def test_verificar_codi_de_sortida_segons_el_veredicte(
    carregada: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    codi_esperat: int,
) -> None:
    monkeypatch.setenv(VAR_MODE, mode)
    codi, _, _ = _cli(_verificar_argv(carregada, PAQUET_FALS, tmp_path / "out"), capsys)
    assert codi == codi_esperat


def test_verificar_no_valida_ho_diu_per_pantalla(
    carregada: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_MODE, "no_valida")
    _, out, err = _cli(_verificar_argv(carregada, PAQUET_FALS, tmp_path / "out"), capsys)
    assert "NO VALIDA" in out
    assert MARCADOR_FALS not in out + err


def test_verificar_valida_ho_diu_per_pantalla(
    carregada: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_MODE, "valida")
    _, out, _ = _cli(_verificar_argv(carregada, PAQUET_FALS, tmp_path / "out"), capsys)
    assert "VALIDA" in out
    assert "NO VALIDA" not in out


def test_verificar_exporta_la_proposta_a_out_dir(
    carregada: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_MODE, "valida")
    sortida = tmp_path / "out"
    _cli(_verificar_argv(carregada, PAQUET_FALS, sortida), capsys)
    assert (sortida / "partida.csv").read_bytes() == PROPOSTA_FIXTURE.read_bytes()


def test_verificar_error_no_mostra_traca_ni_la_sortida_del_verificador(
    carregada: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_MODE, "error")
    codi, out, err = _cli(_verificar_argv(carregada, PAQUET_FALS, tmp_path / "out"), capsys)
    assert codi == 2
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert MARCADOR_FALS not in out + err


def test_verificar_amb_variables_denvironment(
    carregada: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(VAR_MODE, "valida")
    monkeypatch.setenv(VAR_PAQUET, str(PAQUET_FALS))
    monkeypatch.setenv(VAR_VERIFICADOR, str(VERIFICADOR_FALS))
    argv = ["--db", str(carregada), "verificar", "--versio", "partida", "--out-dir", str(tmp_path / "out")]
    assert _cli(argv, capsys)[0] == 0


def test_verificar_versio_inexistent_surt_2(
    carregada: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = _verificar_argv(carregada, PAQUET_FALS, tmp_path / "out")
    argv[argv.index("partida")] = "no_existeix"
    codi, _, err = _cli(argv, capsys)
    assert codi == 2
    assert err.startswith("error:")


# --- uso incorrecto y formato de errores ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["desconegut"], id="subcomanda-inexistent"),
        pytest.param(["--db", "{db}", "export"], id="export-sense-versio"),
        pytest.param(["--db", "{db}", "verificar"], id="verificar-sense-versio"),
    ],
)
def test_us_incorrecte_surt_amb_codi_2(carregada: Path, capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    codi, _, _ = _cli([a.format(db=str(carregada)) for a in argv], capsys)
    assert codi == 2


@pytest.mark.parametrize(
    "plantilla",
    [
        pytest.param(["--db", "{db}", "load", "--paquet", "{paquet}"], id="load-ja-carregada"),
        pytest.param(["--db", "{db}", "export", "--versio", "no_existeix"], id="export-versio-inexistent"),
        pytest.param(["--db", "{db}", "export", "--versio", "../x"], id="export-versio-amb-recorregut"),
        pytest.param(["--db", "{db}", "load"], id="load-sense-paquet"),
        pytest.param(["migrate"], id="sense-bd"),
        pytest.param(
            [
                "--db",
                "{db}",
                "verificar",
                "--versio",
                "no_existeix",
                "--paquet",
                "{paquet}",
                "--verificador",
                "{verificador}",
                "--out-dir",
                "{sortida}",
            ],
            id="verificar-versio-inexistent",
        ),
    ],
)
def test_errors_son_una_linia_error_sense_traca(
    carregada: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    plantilla: list[str],
) -> None:
    argv = [
        a.format(
            db=str(carregada),
            paquet=str(PAQUET_FALS),
            verificador=str(VERIFICADOR_FALS),
            sortida=str(tmp_path / "out"),
        )
        for a in plantilla
    ]
    codi, _, err = _cli(argv, capsys)
    assert codi == 2
    assert err.startswith("error:")
    assert "Traceback" not in err
