# Benchmark summary

Budget T = 300 s. Hard counted = counted verifier violations without R5-FALTA, plus r5_extra.

## Medians per strategy

| strategy | runs | feasible | wall_s | hard_counted | hores_mortes_min | canvis_franja | canvis_aula | r6_canvis_te_paul_fora_passadis |
|---|---|---|---|---|---|---|---|---|
| hybrid | 1 | 0 | 78.75 |  |  |  |  |  |
| portfolio | 1 | 0 | 1.562 |  |  |  |  |  |

## Acceptance (plan §8, vs hybrid)

| strategy | criterion | status | detail |
|---|---|---|---|
| portfolio | feasibility | PASS | 0/1 feasible vs 0/1 hybrid |
| portfolio | hard_counted | N/A | no official data |
| portfolio | fixed_rules | N/A | no official data |
| portfolio | hores_mortes | N/A | missing data |
| portfolio | canvis_franja | N/A | missing data |
| portfolio | wall | PASS | max 1.6s (limit 315s) |
