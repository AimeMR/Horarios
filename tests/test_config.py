from pathlib import Path

import pytest

from extractor.config import ruta_db, ruta_paquet, ruta_verificador
from extractor.errors import ConfigError


@pytest.fixture(autouse=True)
def entorn_net(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("HORARIS_DB", "HORARIS_PAQUET", "HORARIS_VERIFICADOR"):
        monkeypatch.delenv(variable, raising=False)


def test_ruta_db_argument_guanya_a_la_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HORARIS_DB", str(tmp_path / "entorn.db"))
    assert ruta_db(str(tmp_path / "arg.db")) == tmp_path / "arg.db"


def test_ruta_db_usa_la_variable_sense_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HORARIS_DB", str(tmp_path / "entorn.db"))
    assert ruta_db() == tmp_path / "entorn.db"


def test_ruta_db_falta_nomena_la_variable() -> None:
    with pytest.raises(ConfigError, match="HORARIS_DB"):
        ruta_db()


def test_variable_buida_compta_com_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HORARIS_DB", "")
    with pytest.raises(ConfigError, match="HORARIS_DB"):
        ruta_db()


def test_ruta_paquet_argument_guanya_a_la_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entorn = tmp_path / "entorn"
    arg = tmp_path / "arg"
    entorn.mkdir()
    arg.mkdir()
    monkeypatch.setenv("HORARIS_PAQUET", str(entorn))
    assert ruta_paquet(str(arg)) == arg


def test_ruta_paquet_usa_la_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HORARIS_PAQUET", str(tmp_path))
    assert ruta_paquet() == tmp_path


def test_ruta_paquet_falta_nomena_la_variable() -> None:
    with pytest.raises(ConfigError, match="HORARIS_PAQUET"):
        ruta_paquet()


def test_ruta_paquet_carpeta_inexistent(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="HORARIS_PAQUET"):
        ruta_paquet(str(tmp_path / "no-existeix"))


def test_ruta_paquet_fitxer_no_es_carpeta(tmp_path: Path) -> None:
    fitxer = tmp_path / "fitxer.txt"
    fitxer.write_text("x", encoding="utf-8")
    with pytest.raises(ConfigError, match="HORARIS_PAQUET"):
        ruta_paquet(str(fitxer))


def test_ruta_verificador_per_defecte_es_el_pare_del_paquet(tmp_path: Path) -> None:
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    assert ruta_verificador(paquet=paquet) == tmp_path


def test_ruta_verificador_per_defecte_amb_paquet_de_l_entorn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    monkeypatch.setenv("HORARIS_PAQUET", str(paquet))
    assert ruta_verificador() == tmp_path


def test_ruta_verificador_argument_guanya_a_la_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entorn = tmp_path / "entorn"
    arg = tmp_path / "arg"
    entorn.mkdir()
    arg.mkdir()
    monkeypatch.setenv("HORARIS_VERIFICADOR", str(entorn))
    assert ruta_verificador(str(arg)) == arg


def test_ruta_verificador_usa_la_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HORARIS_VERIFICADOR", str(tmp_path))
    assert ruta_verificador(paquet=tmp_path / "ignorat") == tmp_path


def test_ruta_verificador_carpeta_inexistent(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="HORARIS_VERIFICADOR"):
        ruta_verificador(str(tmp_path / "no-existeix"))


def test_ruta_verificador_sense_res_falla_pel_paquet() -> None:
    with pytest.raises(ConfigError, match="HORARIS_PAQUET"):
        ruta_verificador()
