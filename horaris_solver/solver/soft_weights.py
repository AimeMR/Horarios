"""Soft-objective weights (Rule 9). Higher = more important to minimize."""

# Phase 1 — minimize
WEIGHT_HORES_MORTES = 10  # per minute of same-turn gap
WEIGHT_CANVI_DIA = 200  # per activity that leaves partida weekday
WEIGHT_CANVI_HORA = 2  # per 30 minutes away from partida start

# Phase 2 — minimize (room hops / deviation)
WEIGHT_FORA_PASSADIS = 50  # TE↔PAUL consecutive, different passadís
WEIGHT_CANVI_AULA = 5  # room ≠ aula_partida
