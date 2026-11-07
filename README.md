# Horarios (UAB THE HACK! 2026)

- **`extractor/`** — migraciones SQLite + carga del paquet CSV (rama `feat/aime-bd`).
- **`horaris_solver/`** — solver OR-Tools CP-SAT (rama `Enric`): greedy + Phase1 día/hora + Phase2 aulas.

Motor de BD: **SQLite** (`HORARIS_DB`), no MySQL.

## Setup

```bash
cp .env.example .env
# Ajusta HORARIS_PAQUET / HORARIS_DB / HORARIS_VERIFICADOR
uv sync --group dev
```

Cargar BD (extractor):

```bash
uv run --env-file .env extractor migrate
uv run --env-file .env extractor load
```

## Solver

Estrategias: `hybrid` (greedy + CP-SAT `AddHint`; se queda el greedy si CP-SAT es UNKNOWN/INFEASIBLE), `greedy`, `cpsat`.

CSV (sin BD):

```bash
uv run python -m horaris_solver solve \
  --paquet ./repte-horaris-escola/paquet \
  --out ./out/proposta_s1.csv \
  --semestre 1 \
  --strategy hybrid \
  --max-time 300
```

Desde SQLite:

```bash
uv run --env-file .env python -m horaris_solver solve \
  --db ./horaris.db \
  --out ./out/proposta_s1.csv \
  --semestre 1 \
  --curs 1r \
  --strategy hybrid \
  --max-time 180
```

Lots S1 (1r+2n mañana, 3r+4t/M/? tarde). Si el primario de mañana falla, corre la escalera diagnóstica (1r, 2n sin GEET/GEST, GEET+GEST):

```bash
uv run python scripts/run_s1_batches.py \
  --db ./horaris.db \
  --out-dir ./out/s1 \
  --conclusions ./out/s1/conclusions.md \
  --strategy hybrid \
  --max-time 180
```

Ventanas: mañana 08:30–14:30, tarde 15:00–21:00.

## Tests

```bash
uv run pytest
```
