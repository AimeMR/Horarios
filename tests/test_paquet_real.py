"""Comprobación local con el paquete REAL del reto (T10). Nunca corre en CI.

Se activa solo si está definida HORARIS_PAQUET (carpeta `paquet/`); sin ella, todo el módulo se salta. Los tests que
lanzan el verificador real o importan `horaris.model` necesitan además HORARIS_VERIFICADOR (carpeta que contiene
`horaris/`); sin ella, solo se saltan esos.

Reglas: los asserts no vuelcan filas del paquete (solo recuentos, hashes, longitudes, códigos de grupo y veredictos).
El paquete no se lee directamente: solo lo lee el extractor y el verificador oficial.
"""

import hashlib
import importlib
import json
import os
import subprocess  # nosec B404 - tests excluidos de bandit; el subproceso es lista de argumentos sin shell
import sys
from collections.abc import Iterator, Mapping
from contextlib import closing
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from extractor.db import connect
from extractor.export import exportar
from extractor.load import carregar
from extractor.migrate import pujar
from extractor.verificador import ResultatVerificacio, verificar
from tests.conftest import comptar, consulta

VAR_PAQUET = "HORARIS_PAQUET"
VAR_VERIFICADOR = "HORARIS_VERIFICADOR"
PAQUET_REAL = os.environ.get(VAR_PAQUET)
VERIFICADOR_REAL = os.environ.get(VAR_VERIFICADOR)

pytestmark = pytest.mark.skipif(
    not PAQUET_REAL,
    reason=f"Falta {VAR_PAQUET}: comprobación local con el paquete real (nunca en CI)",
)
requereix_verificador = pytest.mark.skipif(
    not VERIFICADOR_REAL,
    reason=f"Falta {VAR_VERIFICADOR}: este test usa el verificador oficial",
)

TIMEOUT_VERIFICADOR_S = 900
SEPARADOR_ID_GRUP = "·"
VIGENT_DES_DE_ESPERAT = "2026-09-01"
ID_ESCENARI_GRAU_NOU = "grau-nou-40"
NIVELL_MASTER_ESPERAT = frozenset({"MRICSE", "MEBA", "MET"})
VEREDICTE_ESPERAT = "NO VALIDA"
CODIS_SORTIDA_VERIFICADOR = (0, 1)
MAX_IDS_EN_MISSATGE = 5


class _SessioVerificador(Protocol):
    @property
    def codi(self) -> str: ...

    @property
    def grup(self) -> str: ...

    @property
    def linia(self) -> str: ...


class _BaseVerificador(Protocol):
    @property
    def sessions(self) -> Mapping[str, _SessioVerificador]: ...


class _CarregaBase(Protocol):
    def __call__(self, paquet: Path) -> _BaseVerificador: ...


@pytest.fixture(scope="module")
def paquet() -> Path:
    return Path(cast(str, PAQUET_REAL))


@pytest.fixture(scope="module")
def verificador() -> Path:
    return Path(cast(str, VERIFICADOR_REAL))


@pytest.fixture(scope="module")
def bd_real(tmp_path_factory: pytest.TempPathFactory, paquet: Path) -> Path:
    """Carga el paquete real UNA vez en una BD temporal (la carga tarda)."""
    bd = tmp_path_factory.mktemp("paquet_real") / "horaris.db"
    with closing(connect(bd)) as conn:
        pujar(conn)
        carregar(conn, paquet)
    return bd


@pytest.fixture(scope="module")
def model_verificador(verificador: Path) -> Iterator[_CarregaBase]:
    """Importa `horaris.model` del verificador real y lo deja fuera de sys.path y sys.modules al terminar."""
    with pytest.MonkeyPatch.context() as mp:
        mp.syspath_prepend(str(verificador))
        modul: ModuleType = importlib.import_module("horaris.model")
        carrega = getattr(modul, "carrega_base", None)
        if not callable(carrega):
            pytest.fail("horaris.model no expone carrega_base")
        yield cast(_CarregaBase, carrega)
    for nom in list(sys.modules):
        if nom == "horaris" or nom.startswith("horaris."):
            del sys.modules[nom]


def _veredicte_de_json(informe: Path) -> str:
    dades: object = json.loads(informe.read_text(encoding="utf-8"))
    assert isinstance(dades, dict), "el informe no es un objeto JSON"
    veredicte = dades.get("veredicte")
    assert isinstance(veredicte, str), "el informe no tiene veredicto de texto"
    return veredicte


def _sha256(camí: Path) -> str:
    return hashlib.sha256(camí.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def informe_directe(tmp_path_factory: pytest.TempPathFactory, paquet: Path, verificador: Path) -> Path:
    """Lanza el verificador real sobre el proposta_partida.csv original (sin pasar por nuestra BD)."""
    carpeta = tmp_path_factory.mktemp("verificador_directe")
    informe = carpeta / "original.json"
    # Lista de argumentos sin shell: ejecutable fijo (sys.executable) y módulo fijo (horaris check).
    completat = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "horaris",
            "check",
            str(paquet / "proposta_partida.csv"),
            "--paquet",
            str(paquet),
            "--json",
            str(informe),
        ],
        cwd=str(verificador),
        shell=False,
        timeout=TIMEOUT_VERIFICADOR_S,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    # Código 2 = entrada ilegible. La salida del verificador no se muestra: podría llevar datos.
    assert completat.returncode in CODIS_SORTIDA_VERIFICADOR, "el verificador no ha podido leer la propuesta"
    return informe


# --- recuentos y restricciones de la BD ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("consulta_sql", "esperat"),
    [
        pytest.param("SELECT COUNT(*) FROM sessio", 17504, id="sessio"),
        pytest.param("SELECT COUNT(*) FROM sessio WHERE id_escenari IS NULL", 17026, id="sessio-base"),
        pytest.param("SELECT COUNT(*) FROM aula", 61, id="aula"),
        pytest.param("SELECT COUNT(*) FROM grup", 1339, id="grup"),
        pytest.param("SELECT COUNT(*) FROM activitat", 1930, id="activitat"),
        pytest.param("SELECT COUNT(*) FROM calendari", 32, id="calendari"),
        pytest.param("SELECT COUNT(*) FROM pla_estudis", 12, id="pla_estudis"),
        pytest.param("SELECT COUNT(*) FROM titulacio", 11, id="titulacio"),
        pytest.param("SELECT COUNT(*) FROM versio_horari", 1, id="versio_horari"),
        pytest.param("SELECT COUNT(*) FROM assignacio", 17026, id="assignacio"),
        pytest.param("SELECT COUNT(*) FROM escenari", 2, id="escenari"),
        pytest.param("SELECT COUNT(*) FROM tancament_aula", 2, id="tancament_aula"),
        pytest.param("SELECT COUNT(*) FROM cancellacio", 1, id="cancellacio"),
        pytest.param("SELECT COUNT(*) FROM canvi_alumnes", 1, id="canvi_alumnes"),
    ],
)
def test_recompte_de_taula(bd_real: Path, consulta_sql: str, esperat: int) -> None:
    with closing(connect(bd_real)) as conn:
        assert comptar(conn, consulta_sql) == esperat


def test_sessions_del_grau_nou_son_478(bd_real: Path) -> None:
    with closing(connect(bd_real)) as conn:
        assert comptar(conn, "SELECT COUNT(*) FROM sessio WHERE id_escenari = ?", (ID_ESCENARI_GRAU_NOU,)) == 478


def test_foreign_key_check_no_retorna_cap_infraccio(bd_real: Path) -> None:
    with closing(connect(bd_real)) as conn:
        infraccions = consulta(conn, "PRAGMA foreign_key_check")
    assert len(infraccions) == 0, "hay incumplimientos de clave foránea"


def test_totes_les_docencies_vigents_des_de_2026_09_01(bd_real: Path) -> None:
    with closing(connect(bd_real)) as conn:
        total = comptar(conn, "SELECT COUNT(*) FROM docencia")
        diferents = comptar(
            conn, "SELECT COUNT(*) FROM docencia WHERE vigent_des_de IS NOT ?", (VIGENT_DES_DE_ESPERAT,)
        )
    assert total > 0
    assert diferents == 0, "hay docencias con otra fecha de vigencia"


def test_titulacions_de_master_son_exactament_mricse_meba_met(bd_real: Path) -> None:
    with closing(connect(bd_real)) as conn:
        trobades = {str(fila[0]) for fila in consulta(conn, "SELECT codi FROM titulacio WHERE nivell = ?", ("master",))}
    faltants = NIVELL_MASTER_ESPERAT - trobades
    sobrants = trobades - NIVELL_MASTER_ESPERAT
    assert len(faltants) == 0, f"faltan {len(faltants)} titulaciones de máster"
    assert len(sobrants) == 0, f"sobran {len(sobrants)} titulaciones de máster"


def test_id_grup_teoria_de_102683_paul_311_es_te_31(bd_real: Path) -> None:
    """Caso ambiguo: TE/31 y TE/310 son de la línea 31; la regla elige TE/31 por número exacto."""
    with closing(connect(bd_real)) as conn:
        filas = consulta(
            conn,
            "SELECT id_grup_teoria FROM grup WHERE id_grup = ?",
            (f"102683{SEPARADOR_ID_GRUP}PAUL/311",),
        )
    assert len(filas) == 1, "no existe el subgrupo 102683·PAUL/311"
    assert filas[0][0] == f"102683{SEPARADOR_ID_GRUP}TE/31"


# --- ida y vuelta y verificador ------------------------------------------------------------------------------


def test_export_partida_es_byte_a_byte_el_paquet(bd_real: Path, paquet: Path, tmp_path: Path) -> None:
    desti = tmp_path / "partida.csv"
    with closing(connect(bd_real)) as conn:
        exportar(conn, "partida", desti)
    original = paquet / "proposta_partida.csv"
    assert desti.stat().st_size == original.stat().st_size, "la longitud del CSV exportado difiere"
    assert _sha256(desti) == _sha256(original), "el CSV exportado difiere del original"


@requereix_verificador
def test_verificar_partida_dona_el_mateix_veredicte_que_el_directe(
    bd_real: Path,
    paquet: Path,
    verificador: Path,
    tmp_path: Path,
    informe_directe: Path,
) -> None:
    with closing(connect(bd_real)) as conn:
        resultat: ResultatVerificacio = verificar(conn, "partida", paquet, verificador, tmp_path / "sortida")
    assert resultat.veredicte == _veredicte_de_json(informe_directe)
    assert _veredicte_de_json(resultat.informe) == _veredicte_de_json(informe_directe)


@requereix_verificador
def test_veredicte_del_verificador_real_es_no_valida(informe_directe: Path) -> None:
    assert _veredicte_de_json(informe_directe) == VEREDICTE_ESPERAT


# --- regla de línea idéntica a la del verificador ------------------------------------------------------------


@requereix_verificador
def test_linia_de_cada_sessio_coincideix_amb_la_del_verificador(
    bd_real: Path, paquet: Path, model_verificador: _CarregaBase
) -> None:
    base = model_verificador(paquet)
    sessions = base.sessions
    with closing(connect(bd_real)) as conn:
        linies: dict[str, str] = {
            str(fila[0]): str(fila[1]) for fila in consulta(conn, "SELECT id_grup, linia FROM grup")
        }
        nostres_base = comptar(conn, "SELECT COUNT(*) FROM sessio WHERE id_escenari IS NULL")
    assert len(sessions) == nostres_base, "el número de sesiones base no coincide"

    discrepancies: list[str] = []
    for sessio in sessions.values():
        id_grup = f"{sessio.codi}{SEPARADOR_ID_GRUP}{sessio.grup}"
        if linies.get(id_grup) != sessio.linia:
            discrepancies.append(id_grup)
    discrepancies.sort()
    mostra = ", ".join(discrepancies[:MAX_IDS_EN_MISSATGE])
    assert len(discrepancies) == 0, f"{len(discrepancies)} discrepancias de línea (id_grup: {mostra})"
