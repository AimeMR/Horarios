# Horarios (UAB THE HACK! 2026)

- **`extractor/`** — migraciones SQLite + carga del paquet CSV (rama `feat/aime-bd`).
- **`horaris_solver/`** — solver OR-Tools CP-SAT (rama `Enric`): Phase1 día/hora + Phase2 aulas + soft Rule 9.

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

CSV (sin BD):

```bash
uv run python -m horaris_solver solve \
  --paquet ./repte-horaris-escola/paquet \
  --out ./out/proposta_s1.csv \
  --semestre 1 \
  --max-time 300
```

Desde SQLite:

```bash
uv run --env-file .env python -m horaris_solver solve \
  --db ./horaris.db \
  --out ./out/proposta_s1.csv \
  --semestre 1 \
  --max-time 300
```

## Tests

```bash
uv run pytest
```
