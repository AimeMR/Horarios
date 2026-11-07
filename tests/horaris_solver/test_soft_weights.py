from horaris_solver.solver.passadis import passadis
from horaris_solver.solver.soft_weights import WEIGHT_HORES_MORTES


def test_passadis_espina_planta() -> None:
    assert passadis("Q1/1011") == "Q1/1"
    assert passadis("Q4/0007") == "Q4/0"


def test_gap_weight_positive() -> None:
    assert WEIGHT_HORES_MORTES > 0
