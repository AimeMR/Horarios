# Horarios

Reto de horarios de la UAB THE HACK! 2026. Este repo genera la base de datos SQLite a partir del paquete del reto.
Ahora mismo tiene dos capas: el esquema SQLite (migraciones) y el extractor en Python que lo crea y lo carga. El
solver en C++, el backend en Node y el frontend en React llegarán después.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (gestor de Python y de dependencias).
- Git.
- Python 3.12: lo instala uv solo la primera vez (lee `.python-version`). Da igual qué Python tengas en el sistema;
  lanza siempre los comandos con `uv run`.
- El material del reto, la carpeta `repte-horaris-escola/` (con `paquet/` y `horaris/`), copiado en la raíz del
  repo. **No se versiona** (ya está en `.gitignore`).

```
Horarios/
├── repte-horaris-escola/   <- lo copias tú; no se sube
│   ├── paquet/
│   └── horaris/
├── db/migrations/
├── extractor/
└── ...
```

## Puesta en marcha

1. Copia la configuración y ajusta las rutas si tu material está en otro sitio:

   ```powershell
   # PowerShell
   Copy-Item .env.example .env
   ```

   ```bash
   # Git Bash
   cp .env.example .env
   ```

   | Variable | Qué es | Valor de ejemplo |
   |---|---|---|
   | `HORARIS_PAQUET` | Carpeta `paquet/` del reto | `./repte-horaris-escola/paquet` |
   | `HORARIS_DB` | Fichero SQLite que se crea | `./horaris.db` |
   | `HORARIS_VERIFICADOR` | Carpeta que contiene `horaris/` (el verificador oficial). Si falta, se usa la carpeta padre de `HORARIS_PAQUET` | `./repte-horaris-escola` |

2. Instala y crea la BD (igual en PowerShell y en Git Bash):

   ```bash
   uv sync
   uv run --env-file .env extractor setup
   ```

`setup` aplica las migraciones pendientes y carga el paquete (la carga va en una sola transacción: o entra todo o
nada). Al terminar imprime cuántas filas tiene cada tabla.

Sin `.env`, pasando las rutas a mano:

```bash
uv run extractor --db horaris.db setup --paquet repte-horaris-escola/paquet
```

Las rutas se resuelven así: primero el argumento (`--db`, `--paquet`, `--verificador`) y, si no está, la variable
de entorno. El extractor no lee `.env` por su cuenta: hace falta `--env-file .env` (o definir las variables en la
shell).

## Comandos

Todos se lanzan como `uv run --env-file .env extractor [--db RUTA] COMANDO [opciones]`. `--db` va **antes** del
subcomando.

| Comando | Qué hace | Ejemplo |
|---|---|---|
| `setup [--paquet RUTA] [--reset]` | `migrate` + `load` | `uv run --env-file .env extractor setup` |
| `migrate` | Aplica las migraciones pendientes | `uv run --env-file .env extractor migrate` |
| `migrate --down N` | Revierte las N migraciones más recientes. Ahora solo hay una: `--down 1` borra todas las tablas | `uv run --env-file .env extractor migrate --down 1` |
| `load [--paquet RUTA] [--reset]` | Carga el paquete. Si la BD ya tiene datos, falla sin tocar nada; con `--reset` vacía las tablas y vuelve a cargar | `uv run --env-file .env extractor load --reset` |
| `export --versio NOM [--out RUTA]` | Exporta una versión de horario al CSV de entrega (por defecto, `out/NOM.csv`) | `uv run --env-file .env extractor export --versio partida --out out/partida.csv` |
| `verificar --versio NOM [--paquet RUTA] [--verificador RUTA] [--out-dir RUTA] [--timeout SEGUNDOS]` | Exporta la versión y la pasa por el verificador oficial. Deja en `out/` el CSV, `NOM.informe.json` y `NOM.violacions.csv`, y guarda el veredicto en la BD. Timeout por defecto: 900 s | `uv run --env-file .env extractor verificar --versio partida` |

La versión `partida` es la propuesta de partida del paquete; se crea al cargar. Su veredicto esperado es
`NO VALIDA`.

Códigos de salida:

| Código | Significado |
|---|---|
| 0 | Todo bien (en `verificar`: veredicto `VALIDA`) |
| 1 | `verificar` ha terminado y el veredicto es `NO VALIDA` |
| 2 | Error (ruta que falta, BD ya cargada, versión que no existe...). El mensaje sale por stderr |

## Qué se sube y qué no

Los datos del paquete están **pseudonimizados, no anonimizados**: se pueden volver a asociar a personas. Por eso
nunca se suben:

| No se sube | Por qué |
|---|---|
| `repte-horaris-escola/` | Es el paquete del reto (datos y verificador) |
| `*.db`, `*.db-*`, `*.sqlite*` | La BD contiene todos los datos del paquete |
| `out/` | Los CSV e informes exportados contienen datos del paquete |
| `.env`, `.env.*` | Configuración local de cada uno (`.env.example` sí se sube) |

Todo esto ya está en `.gitignore`. Antes de cada commit, mira `git status --short`.

- `--out` y `--out-dir` aceptan cualquier ruta: exporta siempre dentro de `out/` (o de otra carpeta ignorada). Un CSV o
  informe exportado a una carpeta versionada acabaría en el repo con datos del paquete.
- `verificar` ejecuta el código Python de la carpeta `--verificador` / `HORARIS_VERIFICADOR`: apúntala solo al
  verificador oficial del reto.

Lo que sí se sube es cómo generarlo: las migraciones (`db/migrations/`), el extractor (`extractor/`), los tests con
datos **falsos** (`tests/fixtures/`, inventados con las mismas cabeceras que el paquete) y el CI
(`.github/workflows/ci.yml`).

## Desarrollo

Lo mismo que ejecuta el CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
uv run bandit -q -c pyproject.toml -r extractor
```

### Comprobación local con el paquete real

`tests/test_paquet_real.py` carga el paquete real, comprueba los recuentos, la ida y vuelta byte a byte de la
propuesta de partida y el veredicto del verificador oficial. **Nunca corre en CI**: sin las dos variables se salta
entero.

```powershell
# PowerShell
$env:HORARIS_PAQUET = "repte-horaris-escola/paquet"
$env:HORARIS_VERIFICADOR = "repte-horaris-escola"
uv run pytest tests/test_paquet_real.py -rs
```

```bash
# Git Bash
export HORARIS_PAQUET=repte-horaris-escola/paquet
export HORARIS_VERIFICADOR=repte-horaris-escola
uv run pytest tests/test_paquet_real.py -rs
```

También vale `uv run --env-file .env pytest tests/test_paquet_real.py -rs`. Con `-rs` pytest dice el motivo si se
salta.

## Migraciones

- Están en `db/migrations/`, con el formato `NNNN_nombre.up.sql` y `NNNN_nombre.down.sql` (cuatro cifras, sin
  huecos ni repetidos, nombre en minúsculas con `_`). Cada `up` necesita su `down`.
- Cada migración se aplica en su propia transacción y queda registrada en la tabla `schema_migrations` con el
  sha256 de su `up`.
- **No edites una migración ya aplicada**: el runner detecta que el sha256 ha cambiado y falla. Para cambiar el
  esquema, crea una migración nueva (`0002_...`).
- Toda conexión a la BD tiene que activar `PRAGMA foreign_keys = ON` (Python, Node y C++). SQLite lo trae apagado
  por defecto y no se puede guardar en el fichero ni en la migración. En Python ya lo hace `extractor.db.connect()`.

## Windows

Si en la consola salen caracteres raros (`migraci�n`), activa el modo UTF-8 de Python en esa sesión:

```powershell
# PowerShell
$env:PYTHONUTF8 = 1
```

```bash
# Git Bash
export PYTHONUTF8=1
```
