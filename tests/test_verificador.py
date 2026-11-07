"""Tests de extractor/verificador.py con el verificador FALSO (tests/fixtures/verificador_fals), nunca el real.

El falso escribe el JSON con los argumentos recibidos y el comportamiento lo elige HORARIS_FALS_MODE.
BD temporal ya migrada con filas inventadas (aula Q1/9001, assignatura 900001, sessions S90001 y S90002).
"""

import dataclasses
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from extractor.verificador import PATRO_ESCENARI, ResultatVerificacio, verificar

from extractor.db import connect
from extractor.errors import ExportError, VerificadorError
from extractor.migrate import DIR_MIGRACIONS, pujar

ID_GRUP = "900001·TE/21"
DIR_FALS = Path(__file__).resolve().parent / "fixtures" / "verificador_fals"
MARCADOR_FALS = "DADA-FALSA-9001"  # lo escribe el falso en stderr en modo error; no debe llegar al mensaje


def _bd_basica(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO aula (codi) VALUES ('Q1/9001')")
    conn.execute("INSERT INTO assignatura (codi, nom) VALUES ('900001', 'Assignatura Falsa 1')")
    conn.execute(
        "INSERT INTO grup (id_grup, codi, grup, tipus, numero, linia, alumnes_origen, torn_requerit) "
        "VALUES (?, '900001', 'TE/21', 'TE', '21', '21', 'sigma', 'mati')",
        (ID_GRUP,),
    )
    for id_sessio in ("S90001", "S90002"):
        conn.execute(
            "INSERT INTO sessio (id_sessio, id_grup, setmana, durada_min, data_partida, dia_partida, h_ini_partida) "
            "VALUES (?, ?, '2027-W03', 60, '2027-01-18', 'L', '08:30')",
            (id_sessio, ID_GRUP),
        )


def _versio(
    conn: sqlite3.Connection,
    id_versio: int,
    nom: str,
    *,
    semestre: int | None = None,
    mode: str = "complet",
    id_escenari: str | None = None,
    id_referencia: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO versio_horari (id_versio, nom, id_versio_referencia, id_escenari, semestre, mode) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (id_versio, nom, id_referencia, id_escenari, semestre, mode),
    )
    conn.execute(
        "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula) VALUES (?, 'S90001', 'L', '08:30', 'Q1/9001')",
        (id_versio,),
    )
    conn.execute(
        "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula) VALUES (?, 'S90002', 'M', '16:00', NULL)",
        (id_versio,),
    )


def _escenari(conn: sqlite3.Connection, id_escenari: str) -> None:
    conn.execute(
        "INSERT INTO escenari (id_escenari, nom, ficticia, descripcio) VALUES (?, ?, 1, NULL)",
        (id_escenari, id_escenari),
    )


def _dades_bd(conn: sqlite3.Connection, nom: str) -> tuple[object, object]:
    fila = conn.execute("SELECT veredicte, informe_json FROM versio_horari WHERE nom = ?", (nom,)).fetchone()
    return fila[0], fila[1]


def _informe(resultat: ResultatVerificacio) -> dict[str, object]:
    dada: object = json.loads(resultat.informe.read_text(encoding="utf-8"))
    assert isinstance(dada, dict)
    return {str(clau): valor for clau, valor in dada.items()}


def _argv(resultat: ResultatVerificacio) -> list[str]:
    argv = _informe(resultat)["argv"]
    assert isinstance(argv, list)
    assert all(isinstance(element, str) for element in argv)
    return [str(element) for element in argv]


def _valor(argv: list[str], opcio: str) -> str | None:
    if opcio not in argv:
        return None
    posicio = argv.index(opcio)
    return argv[posicio + 1]


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connexio = connect(tmp_path / "verificador.db")
    pujar(connexio, DIR_MIGRACIONS)
    _bd_basica(connexio)
    yield connexio
    connexio.close()


@pytest.fixture
def paquet(tmp_path: Path) -> Path:
    arrel = tmp_path / "paquet"
    (arrel / "escenaris" / "contingencies").mkdir(parents=True)
    return arrel


@pytest.fixture
def dir_sortida(tmp_path: Path) -> Path:
    return tmp_path / "sortida"


@pytest.fixture(autouse=True)
def _mode_per_defecte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORARIS_FALS_MODE", raising=False)


def _verifica(
    conn: sqlite3.Connection, versio: str, paquet: Path, dir_sortida: Path, timeout_s: float = 60.0
) -> ResultatVerificacio:
    return verificar(conn, versio, paquet, DIR_FALS, dir_sortida, timeout_s=timeout_s)


# --- resultat i persistència -----------------------------------------------------------------------------------------


def test_mode_no_valida_retorna_codi_1_i_veredicte(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    assert resultat.codi_sortida == 1
    assert resultat.veredicte == "NO VALIDA"


def test_mode_no_valida_crea_proposta_informe_i_violacions(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path
) -> None:
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    assert resultat.proposta == dir_sortida / "partida.csv"
    assert resultat.informe == dir_sortida / "partida.informe.json"
    assert resultat.violacions == dir_sortida / "partida.violacions.csv"
    assert resultat.proposta.is_file()
    assert resultat.informe.is_file()
    assert resultat.violacions.is_file()


def test_mode_no_valida_guarda_veredicte_i_informe_a_la_versio(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path
) -> None:
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    veredicte, informe_json = _dades_bd(conn, "partida")
    assert veredicte == "NO VALIDA"
    assert informe_json == resultat.informe.read_text(encoding="utf-8")


def test_informe_guardat_es_json_valid(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida")
    _verifica(conn, "partida", paquet, dir_sortida)

    _, informe_json = _dades_bd(conn, "partida")
    dada: object = json.loads(str(informe_json))
    assert isinstance(dada, dict)
    assert dada["veredicte"] == "NO VALIDA"


def test_mode_valida_retorna_codi_0_i_veredicte(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORARIS_FALS_MODE", "valida")
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    assert resultat.codi_sortida == 0
    assert resultat.veredicte == "VALIDA"
    assert _dades_bd(conn, "partida")[0] == "VALIDA"


def test_resultat_es_inmutable(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida")
    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    camp = "veredicte"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(resultat, camp, "VALIDA")


# --- argumentos del verificador --------------------------------------------------------------------------------------


def test_argumentos_basiques_proposta_paquet_json_i_violacions(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path
) -> None:
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)
    argv = _argv(resultat)

    assert Path(argv[0]).resolve() == (dir_sortida / "partida.csv").resolve()
    assert Path(str(_valor(argv, "--paquet"))).resolve() == paquet.resolve()
    assert Path(str(_valor(argv, "--json"))).resolve() == resultat.informe.resolve()
    assert Path(str(_valor(argv, "--violacions"))).resolve() == resultat.violacions.resolve()


@pytest.mark.parametrize("semestre", [1, 2])
def test_passa_semestre_si_la_versio_en_te(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, semestre: int
) -> None:
    _versio(conn, 1, "partida", semestre=semestre)

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert _valor(argv, "--semestre") == str(semestre)


def test_sense_semestre_no_passa_l_opcio(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida", semestre=None)

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert "--semestre" not in argv


def test_mode_nomes_aules_passa_nomes_aules(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida", mode="nomes_aules")

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert "--nomes-aules" in argv


def test_mode_complet_no_passa_nomes_aules(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida", mode="complet")

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert "--nomes-aules" not in argv


def test_escenari_passa_la_carpeta_del_paquet(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _escenari(conn, "contingencies")
    _versio(conn, 1, "partida", id_escenari="contingencies")

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    escenari = _valor(argv, "--escenari")
    assert escenari is not None
    assert Path(escenari).resolve() == (paquet / "escenaris" / "contingencies").resolve()


def test_sense_escenari_no_passa_l_opcio(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida", id_escenari=None)

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert "--escenari" not in argv


def test_referencia_exporta_la_versio_de_referencia_i_passa_la_ruta(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path
) -> None:
    _versio(conn, 1, "base")
    _versio(conn, 2, "partida", id_referencia=1)

    resultat = _verifica(conn, "partida", paquet, dir_sortida)
    argv = _argv(resultat)

    referencia = dir_sortida / "base.csv"
    assert referencia.is_file()
    valor = _valor(argv, "--referencia")
    assert valor is not None
    assert Path(valor).resolve() == referencia.resolve()


def test_sense_referencia_no_passa_l_opcio(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida", id_referencia=None)

    argv = _argv(_verifica(conn, "partida", paquet, dir_sortida))

    assert "--referencia" not in argv


def test_el_proces_rep_pythonutf8_a_1(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _versio(conn, 1, "partida")

    resultat = _verifica(conn, "partida", paquet, dir_sortida)

    assert _informe(resultat)["pythonutf8"] == "1"


# --- validació d'entrada: res no s'executa ---------------------------------------------------------------------------


@pytest.mark.parametrize("nom", ["a b", "x;rm", "x&y", "../x", "x/y"])
def test_nom_de_versio_amb_simbols_es_rebutja_abans_de_lancar_res(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, nom: str
) -> None:
    _versio(conn, 1, nom)

    with pytest.raises((VerificadorError, ExportError)):
        _verifica(conn, nom, paquet, dir_sortida)
    assert not (dir_sortida / f"{nom}.informe.json").exists()
    assert _dades_bd(conn, nom) == (None, None)


@pytest.mark.parametrize("id_escenari", ["../fuera", "Contingencies", "a b"])
def test_id_escenari_fora_del_patro_falla(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, id_escenari: str
) -> None:
    (paquet / "fuera").mkdir()
    _escenari(conn, id_escenari)
    _versio(conn, 1, "partida", id_escenari=id_escenari)

    with pytest.raises(VerificadorError):
        _verifica(conn, "partida", paquet, dir_sortida)
    assert not (dir_sortida / "partida.informe.json").exists()


def test_id_escenari_sense_carpeta_falla(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    _escenari(conn, "sense-carpeta")
    _versio(conn, 1, "partida", id_escenari="sense-carpeta")

    with pytest.raises(VerificadorError):
        _verifica(conn, "partida", paquet, dir_sortida)
    assert not (dir_sortida / "partida.informe.json").exists()


@pytest.mark.parametrize("id_escenari", ["a" * 64, "contingencies"])
def test_patro_escenari_accepta_els_limits_valids(id_escenari: str) -> None:
    assert PATRO_ESCENARI.fullmatch(id_escenari) is not None


@pytest.mark.parametrize("id_escenari", ["", "a" * 65, "../x", "A", "a_b", "a b"])
def test_patro_escenari_rebutja_els_valors_invalids(id_escenari: str) -> None:
    assert PATRO_ESCENARI.fullmatch(id_escenari) is None


def test_versio_inexistent_falla(conn: sqlite3.Connection, paquet: Path, dir_sortida: Path) -> None:
    with pytest.raises(VerificadorError):
        _verifica(conn, "no-existeix", paquet, dir_sortida)


# --- errors del proces -----------------------------------------------------------------------------------------------


def test_codi_de_sortida_2_falla_sense_filtrar_la_sortida(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORARIS_FALS_MODE", "error")
    _versio(conn, 1, "partida")

    with pytest.raises(VerificadorError) as excepcio:
        _verifica(conn, "partida", paquet, dir_sortida)

    assert MARCADOR_FALS not in str(excepcio.value)
    assert _dades_bd(conn, "partida") == (None, None)


def test_veredicte_fora_de_la_llista_falla_i_no_es_guarda(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORARIS_FALS_MODE", "veredicte_raro")
    _versio(conn, 1, "partida")

    with pytest.raises(VerificadorError):
        _verifica(conn, "partida", paquet, dir_sortida)

    assert _dades_bd(conn, "partida") == (None, None)


def test_timeout_falla(
    conn: sqlite3.Connection, paquet: Path, dir_sortida: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORARIS_FALS_MODE", "lent")
    _versio(conn, 1, "partida")

    with pytest.raises(VerificadorError):
        _verifica(conn, "partida", paquet, dir_sortida, timeout_s=1)

    assert _dades_bd(conn, "partida") == (None, None)
