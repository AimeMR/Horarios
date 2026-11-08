# Benchmark summary

Budget T = 120 s. Hard counted = counted verifier violations without R5-FALTA, plus r5_extra.

## Medians per strategy

| strategy | runs | feasible | wall_s | hard_counted | hores_mortes_min | canvis_franja | canvis_aula | r6_canvis_te_paul_fora_passadis |
|---|---|---|---|---|---|---|---|---|
| hybrid | 3 | 3 | 20.094 | 0 | 14520 | 175 | 107 | 314 |
| portfolio | 3 | 0 | 0.375 |  |  |  |  |  |

## Acceptance (plan §8, vs hybrid)

| strategy | criterion | status | detail |
|---|---|---|---|
| portfolio | feasibility | FAIL | 0/3 feasible vs 3/3 hybrid |
| portfolio | hard_counted | N/A | no official data |
| portfolio | fixed_rules | N/A | no official data |
| portfolio | hores_mortes | N/A | missing data |
| portfolio | canvis_franja | N/A | missing data |
| portfolio | wall | PASS | max 0.4s (limit 126s) |
