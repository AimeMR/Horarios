# Contrato de interfaces · fase 2 (backend Node + TypeScript)

Escrito por el orquestador. Tests y código se ajustan a ESTAS firmas; si una no encaja, se dice en el informe.
Todo vive en `backend/` (paquete npm propio). ESM (`"type": "module"`), TypeScript `strict` +
`noUncheckedIndexedAccess`, Node >= 22. Imports relativos con extensión `.js` (NodeNext).

La BD la crean SIEMPRE las migraciones del extractor Python (`uv run extractor …` desde la raíz del repo). El backend
**no ejecuta DDL**. Esquema: `db/migrations/0001_esquema_inicial.up.sql`.

## src/config.ts (B1)

```ts
export interface Config {
  readonly dbPath: string;        // HORARIS_DB (obligatoria)
  readonly host: string;          // HOST, por defecto "127.0.0.1"
  readonly port: number;          // PORT, por defecto 3000 (1..65535)
  readonly corsOrigin: string;    // CORS_ORIGIN, por defecto "http://localhost:5173"
  readonly logLevel: "fatal" | "error" | "warn" | "info" | "debug" | "trace" | "silent"; // LOG_LEVEL, por defecto "info"
}
export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config   // zod; error claro si falta/no vale (sin valores)
```

## src/db/connection.ts (B2)

```ts
import type { Database } from "better-sqlite3";
export function openDatabase(path: string, options?: { readonly?: boolean }): Database
```
- `fileMustExist: true` (el backend nunca crea la BD), `pragma foreign_keys = ON` y se comprueba que vale 1 (si no,
  lanza `Error`), `pragma busy_timeout = 5000`. Lectura/escritura por defecto; `readonly` opcional.

## src/domain/ (B3 crea errors.ts; B5/B6 sus tipos)

```ts
// errors.ts
export class NotFoundError extends Error {}         // -> 404 { error: "not_found" }
export class ValidationError extends Error {        // -> 400 { error: "invalid_request", issues: [{ path, message }] }
  constructor(readonly issues: ReadonlyArray<{ path: string; message: string }>) { ... }
}
export class NotImplementedError extends Error {}   // -> 501 { error: "not_implemented" }

// aula.ts (B5)
export type TipusAula = "Aules docents" | "Laboratoris docents" | "Seminaris" | "Aules informàtiques";
export interface Aula { codi: string; edifici: string | null; espina: string; planta: number; tipus: TipusAula | null;
  capacitat: number | null; ordinaria: boolean; integrat: boolean; nomesPlab: boolean; dinsAulari: boolean;
  admetNoves: boolean; descripcio: string | null }

// versio.ts / assignacio.ts (B6)
export interface Versio { id: number; nom: string; idVersioReferencia: number | null; idEscenari: string | null;
  semestre: 1 | 2 | null; mode: "complet" | "nomes_aules"; creadaEl: string;
  veredicte: "VALIDA" | "VALIDA AMB RELAXACIONS DECLARADES" | "NO VALIDA" | null }
export interface Assignacio { idSessio: string; dia: "L" | "M" | "X" | "J" | "V"; hIni: string; aula: string | null;
  data: string | null }
```
Los `issues` de ValidationError llevan la ruta del campo y un mensaje de regla, **nunca el valor recibido**.

## src/http/ (B3)

```ts
// app.ts
export interface AppDeps { readonly db: Database; readonly config: Config; readonly logger: Logger }
export function createApp(deps: AppDeps): express.Express
// routes.ts — SOLO lo edita el orquestador (B7)
export function registerRoutes(router: express.Router, deps: AppDeps): void
// validate.ts
export function parseQuery<T>(schema: z.ZodType<T>, query: unknown): T      // lanza ValidationError
export function parseParams<T>(schema: z.ZodType<T>, params: unknown): T    // lanza ValidationError
// pagination.ts
export const paginationSchema: z.ZodObject<...>  // limit: int 1..500 (por defecto 100), offset: int >= 0 (por defecto 0); coerce desde string
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
// errors.ts
export function notFoundHandler(): express.RequestHandler          // 404 { error: "not_found" }
export function errorHandler(logger: Logger): express.ErrorRequestHandler
//   NotFoundError -> 404; ValidationError -> 400 con issues; NotImplementedError -> 501;
//   JSON mal formado / body demasiado grande -> 400 { error: "invalid_request" };
//   resto -> 500 { error: "internal_error", requestId } y log con el error y requestId (sin cuerpo de la petición).
// logger.ts
export type Logger = pino.Logger
export function createLogger(level: Config["logLevel"]): Logger     // sin serializar req.body
// params.ts (B3) — esquemas compartidos por las features
export const idVersioParamsSchema: z.ZodObject<...>   // { id: int >= 1 } coerce desde string
export const setmanaSchema: z.ZodString               // /^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/
```
Request id: el middleware de `createApp` guarda el id en `res.locals.requestId` y en la cabecera de respuesta
`x-request-id`; `errorHandler` lo lee de ahí (si falta, genera uno). Nunca se toma de la petición del cliente.
`createApp`: `helmet()`, `cors({ origin: config.corsOrigin })` (un solo origen, sin credenciales),
`express.json({ limit: "100kb" })`, `x-powered-by` desactivado, request id (cabecera `x-request-id` de respuesta,
`crypto.randomUUID()`), router con `registerRoutes`, `notFoundHandler`, `errorHandler`.
Ruta `GET /health` → 200 `{ "status": "ok" }` (en `src/features/health/health.controller.ts`, función
`healthRouter(): express.Router`), registrada en `routes.ts`.

Cada feature exporta un router: `export function aulesRouter(deps: AppDeps): express.Router` (B5),
`export function versionsRouter(deps: AppDeps): express.Router` (B6), `informeRouter` (B9), `parrillaRouter` (B10),
`ocupacioRouter` (B11). `routes.ts` los monta en `/health`, `/aules` y `/versions` (B7).

## src/features/aules (B5) · GET /aules

Query: `tipus` (opcional, enum de los 4 `TipusAula`), `capacitat_min` (opcional, int 0..1000), `limit`, `offset`.
Respuesta 200: `Page<AulaDto>`; `AulaDto` = `Aula` (mismas claves camelCase). Orden `codi ASC`. Filtrar por `tipus`
excluye las externas (`tipus` NULL); `capacitat_min` excluye las de capacidad NULL. 400 si la query no vale.
Capas: `aules.repository.ts` (SQL parametrizado, fila→dominio), `aules.service.ts`, `aules.controller.ts`
(valida con zod, dominio→DTO), `aules.dto.ts` (esquemas zod + mapper), `aules.test.ts`.

## src/features/versions (B6)

- `GET /versions` (`limit`, `offset`) → 200 `Page<VersioDto>` ordenado por `id ASC` (sin `informe_json`).
- `GET /versions/:id/assignacions` (`limit`, `offset`) → 200 `Page<AssignacioDto>` ordenado por `idSessio ASC`;
  `:id` entero positivo (si no, 400); versión inexistente → 404.
Mismas 4 capas + test.

## Patrón común de B5, B6, B9, B10 y B11

- Cada feature exporta un router; `routes.ts` (B7) los monta: `/aules` → `aulesRouter`; `/versions` →
  `versionsRouter`, `informeRouter`, `parrillaRouter`, `ocupacioRouter` (estos tres definen rutas `/:id/...`).
- Tests de feature con supertest sobre una mini app: `express().use("/versions", xRouter(deps))` +
  `notFoundHandler()` + `errorHandler(deps.logger)`, con `deps = testDeps()` (BD de fixtures en solo lectura).
- `:id` con `idVersioParamsSchema` (400 si no vale); versión inexistente → 404 `{ error: "not_found" }`. Cada
  repositorio comprueba la existencia con su propia consulta parametrizada.
- Fechas y horas con `src/domain/setmana.ts` (ya existe, lo escribió el orquestador): `DIES`, `Dia`,
  `dillunsDeSetmana`, `diesDeSetmana`, `dataMateixaSetmana`, `minuts`, `hora`.
- **Fecha efectiva** de una asignación: `assignacio.data` si no es NULL (sesión recuperada); si no,
  `dataMateixaSetmana(sessio.data_partida, sessio.dia_partida, assignacio.dia)`. Una asignación pertenece a la
  semana S si `(a.data IS NULL AND s.setmana = S) OR (a.data BETWEEN dilluns(S) AND divendres(S))`.
- Fin de una sesión = `h_ini + sessio.durada_min`.

## src/features/informe (B9) · GET /versions/:id/informe

Lee `versio_horari.veredicte` e `informe_json` (salida `--json` del verificador). El JSON guardado es **dato no
confiable**: se parsea con un esquema zod; si no lo cumple → 500 (log sin el contenido). Respuesta 200:
```jsonc
{ "idVersio": 1, "nom": "partida", "veredicte": "NO VALIDA" | ... | null,
  "informe": null | {
    "restriccions": [ { "regla": "R0-FORMAT", "total": 0, "compten": 0, "declarades": 0, "heretades": 0,
                        "estat": "OK" | "KO" | "REL" } ],   // las 20 reglas de REGLES, en ese orden
    "noAvaluables": [ { "regla": "R1-TORN", "sessions": 3 } ],            // orden por regla
    "objectius": { "horesMortesMin": 0, "desplacamentsAula": 0, "desplacamentsEdifici": 0, "canvisFranja": 0,
                   "canvisAula": 0, "r6AulesTeExtraPerGrup": 0, "r6CanvisTePaulForaPassadis": 0,
                   "sessionsAvaluades": 0, "canvisFranjaVsReferencia": null, "canvisAulaVsReferencia": null },
    "relaxacionsDeclarades": 0, "incomplimentsDeclarats": 0,
    "context": { "semestre": 1 | 2 | null, "nomesAules": false } } }
```
- `informe: null` si `informe_json` es NULL (versión sin verificar).
- `estat`: `KO` si `compten > 0`; si no, `REL` si `declarades > 0`; si no, `OK` (misma marca que el verificador).
  Una regla ausente del JSON sale con ceros y `OK`.
- `REGLES` (constante en `informe.dto.ts`, este orden): R0-FORMAT, R0-HORARI, R1-FIXADA, R1-TORN, R2-FINESTRA,
  R2-CALENDARI, R3-AULA, R3-AFORAMENT, R3-TIPUS, R3-TANCADA, R4-AULA, R4-DOCENT, R4-ALUMNAT, R4-PLAB,
  R4-COMPARTIDA, R5-FALTA, R5-SENSE-AULA, R5-RECUPERACIO, R7-PLAB, R8-RESERVA. Reglas desconocidas del JSON
  se añaden al final en orden alfabético.
- Del `context` del verificador **solo** salen `semestre` y `nomes_aules`: `escenari` es una ruta local y los
  `*_sha256` no los necesita el frontend.
- Claves de entrada del JSON (snake_case): `veredicte`, `restriccions{regla:{total,compten,declarades,heretades}}`,
  `no_avaluables{regla:n}`, `objectius{hores_mortes_min,…,canvis_franja_vs_referencia?,canvis_aula_vs_referencia?}`,
  `relaxacions_declarades`, `incompliments_declarats`, `context{semestre,nomes_aules,…}`. Claves extra se ignoran.
- Tests: la fixture no tiene informe; el test copia la BD de `inject("dbPath")` a un tmp, la abre en escritura con
  `openDatabase`, inserta versiones con `informe_json` válido, sin reglas, con reglas desconocidas y con JSON que
  no cumple el esquema, y monta el router con esa BD.

## src/features/parrilla (B10) · GET /versions/:id/parrilla

Query: `setmana` (obligatoria, `setmanaSchema`) y **al menos uno** de estos filtros (si no hay ninguno → 400),
combinables con AND:
- `aula` `/^[A-Za-z0-9]{1,8}\/[A-Za-z0-9]{1,8}$/`;
- `cohort` `/^[A-Za-z0-9]{1,12}:(1r|2n|3r|4t|M|\?)$/` (vía `assignatura_cohort` del `grup.codi`);
- `profe` `/^[A-Za-z0-9]{1,12}$/` (vía `docencia` vigente en la fecha de partida de la sesión);
- `assignatura` `/^[0-9]{1,12}$/`;
- `grup` = id_grup `/^[0-9]{1,12}·(TE|PAUL|PLAB|SEM)\/[0-9]{1,6}$/`.

Respuesta 200:
```jsonc
{ "idVersio": 1, "setmana": "2026-W38",
  "dies": [ { "dia": "L", "data": "2026-09-14" }, ... ],                  // 5 entradas
  "filtre": { "cohort": "GFA:1r" },                                       // solo los filtros recibidos
  "calendari": [ { "data": "…", "tipus": "festiu", "hIni": null, "hFi": null, "motiu": "…" } ], // de la semana
  "items": [ { "idSessio": "S90005", "data": "2026-09-14", "dia": "L", "hIni": "08:30", "hFi": "10:00",
               "duradaMin": 90, "aula": "Q8/8103",
               "assignatura": { "codi": "900001", "nom": "…" },
               "grup": { "idGrup": "900001·TE/81", "grup": "TE/81", "tipus": "TE" },
               "alumnes": 50, "profes": ["D901"], "cohorts": ["GFA:1r"], "idCompartida": null,
               "fixadaMotiu": null, "moguda": false, "canviAula": false, "recuperada": false } ],
  "truncat": false }
```
- Orden `data, hIni, aula (NULL al final), idSessio`. Máximo 1000 items; si hay más, `truncat: true`.
- `moguda`: `a.data IS NOT NULL OR a.dia <> s.dia_partida OR a.h_ini <> s.h_ini_partida`.
  `canviAula`: `a.aula IS NOT s.aula_partida`. `recuperada`: `a.data IS NOT NULL`.
- `profes` y `cohorts` ordenados ASC, sin duplicados (arrays vacíos si no hay).
- `alumnes` = `grup.alumnes`.

## src/features/ocupacio (B11) · GET /versions/:id/ocupacio

Query: `setmana` (obligatoria), `tipus` (opcional, enum `TipusAula`). Aulas consideradas: `aula.dins_aulari = 1`
(y del `tipus` si se pide), por `codi ASC`. Ventana diaria 08:30–21:00 (750 min, 3750 por semana). Franjas:
13 inicios `08:30, 09:30 … 20:30`; cada una dura 60 min salvo la de 20:30, que acaba a las 21:00.

Respuesta 200:
```jsonc
{ "idVersio": 1, "setmana": "2026-W38", "dies": [ { "dia": "L", "data": "2026-09-14" }, ... ],
  "franges": ["08:30", "09:30", ..., "20:30"],
  "perAula": [ { "codi": "Q8/8103", "edifici": "Q8", "tipus": "Aules docents", "capacitat": 60, "ordinaria": true,
                 "sessions": 3, "minutsOcupats": 270, "minutsDisponibles": 3750, "percentatge": 7.2 } ],
  "perFranja": [ { "dia": "L", "data": "2026-09-14", "franja": "08:30", "ocupades": 1, "lliures": 6,
                   "ordinariesLliures": 2, "reservaOk": true } ] }          // 5 × 13 = 65 entradas, dia y franja
```
- Solo cuentan asignaciones de la semana con `aula` dentro del conjunto considerado.
- `minutsOcupats`: unión de intervalos por aula y día recortada a la ventana (dos sesiones solapadas en la misma
  aula no suman dos veces). `percentatge` = `round(100 * ocupats / disponibles, 1)`. `sessions` = asignaciones.
- Una aula está ocupada en una franja si alguna sesión suya solapa `[inicio, fin)` de la franja.
  `ocupades`/`lliures` se cuentan sobre el conjunto considerado.
- `ordinariesLliures`: aulas `ordinaria = 1` y `dins_aulari = 1` libres en la franja, **sin aplicar el filtro
  `tipus`** (indicador de R8). `reservaOk` = `ordinariesLliures >= 2`.

## src/process/run-process.ts (B4)

```ts
export interface RunOptions { readonly cwd?: string; readonly timeoutMs: number; readonly maxBufferBytes?: number;
  readonly env?: NodeJS.ProcessEnv }
export interface RunResult { readonly exitCode: number; readonly stdout: string; readonly stderr: string }
export class ProcessTimeoutError extends Error {}
export function runProcess(file: string, args: readonly string[], options: RunOptions): Promise<RunResult>
```
`child_process.execFile` (nunca `exec` ni `shell: true`), args en array, `timeout` + `killSignal: "SIGKILL"`,
`maxBuffer` (por defecto 1 MiB), `windowsHide: true`. Código distinto de 0 → se resuelve con `exitCode` (no rechaza);
timeout → `ProcessTimeoutError`; `maxBuffer` superado o error de arranque → rechaza con `Error` genérico.

`src/features/solver/solver.service.ts` y `src/features/verificador/verificador.service.ts`:
```ts
export interface SolverService { executar(versioOrigen: string): Promise<never> }        // lanza NotImplementedError
export interface VerificadorService { verificar(versio: string): Promise<never> }       // lanza NotImplementedError
export function createSolverService(): SolverService
export function createVerificadorService(): VerificadorService
```
Sin rutas expuestas.

## test/ (B2)

`test/global-setup.ts` (Vitest `globalSetup`): crea un directorio temporal, ejecuta desde la raíz del repo
(`path.resolve(__dirname, "../..")`) `uv run extractor --db <tmp>/test.db setup --paquet tests/fixtures/paquet_fals`
con `execFile` (sin shell), y expone la ruta con `provide("dbPath", …)` (Vitest `inject`). Borra el directorio al
terminar. `test/helpers.ts`: `testDeps(): AppDeps` que abre esa BD en modo `readonly` con un logger `silent`.
Los recuentos esperados de las fixtures están en `tests/fixtures/paquet_fals/ESPERAT.md` (aula 12, versio_horari 1,
assignacio 28…).

## package.json scripts (B1)

`dev` (tsx watch src/server.ts), `build` (tsc -p tsconfig.build.json → `dist/`), `start` (node dist/server.js),
`typecheck` (tsc --noEmit), `lint` (eslint .), `test` (vitest run).
