from horaris_solver.solver.passadis import passadis
from horaris_solver.solver.soft_weights import (
    WEIGHT_CANVI_AULA,
    WEIGHT_CANVI_DIA,
    WEIGHT_FORA_PASSADIS,
    WEIGHT_HORES_MORTES,
    WEIGHT_SIN_AULA,
    WEIGHT_SOLAPAMENT_HERETAT,
    WEIGHT_SOLAPAMENT_RELAXAT,
)


def test_passadis_espina_planta() -> None:
    assert passadis("Q1/1011") == "Q1/1"
    assert passadis("Q4/0007") == "Q4/0"


def test_gap_weight_positive() -> None:
    assert WEIGHT_HORES_MORTES > 0


def test_overlap_weights_rank_relaxed_above_inherited() -> None:
    assert WEIGHT_SOLAPAMENT_HERETAT == 50
    assert WEIGHT_SOLAPAMENT_RELAXAT == 1000
    assert WEIGHT_SOLAPAMENT_RELAXAT > WEIGHT_CANVI_DIA > WEIGHT_SOLAPAMENT_HERETAT


def test_unassigned_room_weight_dominates_phase2_terms() -> None:
    assert WEIGHT_SIN_AULA == 100000
    assert WEIGHT_SIN_AULA > WEIGHT_FORA_PASSADIS + WEIGHT_CANVI_AULA
