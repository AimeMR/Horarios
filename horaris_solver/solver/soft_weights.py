"""Soft-objective weights (Rule 9). Higher = more important to minimize."""

# Phase 1 — minimize
WEIGHT_HORES_MORTES = 10  # per minute of same-turn gap
WEIGHT_CANVI_DIA = 200  # per activity that leaves partida weekday
WEIGHT_CANVI_HORA = 2  # per 30 minutes away from partida start
WEIGHT_SOLAPAMENT_HERETAT = 50  # per minute of overlap kept between a pair already overlapping in partida
WEIGHT_SOLAPAMENT_RELAXAT = 1000  # per minute of overlap in the last-resort soft_overlap mode

# Phase 2 — minimize (room hops / deviation)
WEIGHT_FORA_PASSADIS = 50  # TE↔PAUL consecutive, different passadís
WEIGHT_CANVI_AULA = 5  # room ≠ aula_partida
WEIGHT_SIN_AULA = 100000  # per movable session left without room (partial phase 2); dominates all other terms
