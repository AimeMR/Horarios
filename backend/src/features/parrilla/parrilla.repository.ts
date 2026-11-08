import type { Database } from "better-sqlite3";
import type { DiaCalendari, FiltreParrilla, FranjaParrilla } from "../../domain/parrilla.js";
import { ASSIGNACIO_A_SETMANA_SQL, DATA_EFECTIVA_SQL } from "../../db/setmana-sql.js";
import { type Dia, dataEfectiva, horaSenseLimit, minuts } from "../../domain/setmana.js";

interface SessioRow {
  id_sessio: string;
  durada_min: number;
  data_partida: string;
  dia_partida: Dia;
  h_ini_partida: string;
  aula_partida: string | null;
  id_compartida: string | null;
  dia: Dia;
  h_ini: string;
  aula: string | null;
  data: string | null;
  id_grup: string;
  grup: string;
  tipus: string;
  alumnes: number;
  fixada_motiu: string | null;
  codi: string;
  nom: string;
}

interface CalendariRow {
  data: string;
  tipus: string;
  h_ini: string | null;
  h_fi: string | null;
  motiu: string;
}

interface ParellaRow {
  id_sessio: string;
  valor: string;
}

type Params = Record<string, string | number>;

const SELECT_SESSIONS = `
  SELECT s.id_sessio, s.durada_min, s.data_partida, s.dia_partida, s.h_ini_partida, s.aula_partida,
         s.id_compartida, a.dia, a.h_ini, a.aula, a.data,
         g.id_grup, g.grup, g.tipus, g.alumnes, g.fixada_motiu, g.codi, asg.nom
  FROM assignacio a
  JOIN sessio s ON s.id_sessio = a.id_sessio
  JOIN grup g ON g.id_grup = s.id_grup
  JOIN assignatura asg ON asg.codi = g.codi
  WHERE a.id_versio = @idVersio
    AND ${ASSIGNACIO_A_SETMANA_SQL}`;

const ORDRE_SQL = ` ORDER BY ${DATA_EFECTIVA_SQL}, a.h_ini, a.aula IS NULL, a.aula, s.id_sessio`;

const FILTRES_SQL: ReadonlyArray<readonly [keyof FiltreParrilla, string]> = [
  ["aula", "a.aula = @aula"],
  [
    "cohort",
    "EXISTS (SELECT 1 FROM assignatura_cohort ac WHERE ac.codi = g.codi AND ac.id_cohort = @cohort)",
  ],
  [
    "profe",
    `EXISTS (SELECT 1 FROM docencia d WHERE d.id_grup = s.id_grup AND d.id_profe = @profe
            AND d.vigent_des_de <= s.data_partida AND (d.vigent_fins IS NULL OR d.vigent_fins >= s.data_partida))`,
  ],
  ["assignatura", "g.codi = @assignatura"],
  ["grup", "s.id_grup = @grup"],
];

export function versioExisteix(db: Database, idVersio: number): boolean {
  const fila = db.prepare("SELECT 1 AS ok FROM versio_horari WHERE id_versio = ?").get(idVersio);
  return fila !== undefined;
}

function clausesFiltre(filtre: FiltreParrilla): { sql: string; params: Params } {
  const rebuts = Object.entries(filtre).filter((e): e is [string, string] => typeof e[1] === "string");
  const valors = new Map(rebuts);
  let sql = "";
  const params = new Map<string, string>();
  for (const [clau, fragment] of FILTRES_SQL) {
    const valor = valors.get(clau);
    if (valor !== undefined) {
      sql += ` AND ${fragment}`;
      params.set(clau, valor);
    }
  }
  return { sql, params: Object.fromEntries(params) };
}

function placeholders(n: number): string {
  return Array.from({ length: n }, () => "?").join(",");
}

function agrupa(files: readonly ParellaRow[]): Map<string, string[]> {
  const mapa = new Map<string, Set<string>>();
  for (const f of files) {
    const conjunt = mapa.get(f.id_sessio) ?? new Set<string>();
    conjunt.add(f.valor);
    mapa.set(f.id_sessio, conjunt);
  }
  return new Map([...mapa].map(([id, valors]) => [id, [...valors].sort()]));
}

function profesPerSessio(db: Database, ids: readonly string[]): Map<string, string[]> {
  if (ids.length === 0) return new Map();
  const files = db
    .prepare(
      `SELECT s.id_sessio, d.id_profe AS valor
       FROM sessio s
       JOIN docencia d ON d.id_grup = s.id_grup
        AND d.vigent_des_de <= s.data_partida AND (d.vigent_fins IS NULL OR d.vigent_fins >= s.data_partida)
       WHERE s.id_sessio IN (${placeholders(ids.length)})`,
    )
    .all(...ids) as ParellaRow[];
  return agrupa(files);
}

function cohortsPerSessio(db: Database, ids: readonly string[]): Map<string, string[]> {
  if (ids.length === 0) return new Map();
  const files = db
    .prepare(
      `SELECT s.id_sessio, ac.id_cohort AS valor
       FROM sessio s
       JOIN grup g ON g.id_grup = s.id_grup
       JOIN assignatura_cohort ac ON ac.codi = g.codi
       WHERE s.id_sessio IN (${placeholders(ids.length)})`,
    )
    .all(...ids) as ParellaRow[];
  return agrupa(files);
}

function aFranja(row: SessioRow, profes: readonly string[], cohorts: readonly string[]): FranjaParrilla {
  const recuperada = row.data !== null;
  return {
    idSessio: row.id_sessio,
    data: dataEfectiva(row.data, row.data_partida, row.dia_partida, row.dia),
    dia: row.dia,
    hIni: row.h_ini,
    hFi: horaSenseLimit(minuts(row.h_ini) + row.durada_min),
    duradaMin: row.durada_min,
    aula: row.aula,
    assignatura: { codi: row.codi, nom: row.nom },
    grup: { idGrup: row.id_grup, grup: row.grup, tipus: row.tipus },
    alumnes: row.alumnes,
    profes,
    cohorts,
    idCompartida: row.id_compartida,
    fixadaMotiu: row.fixada_motiu,
    moguda: recuperada || row.dia !== row.dia_partida || row.h_ini !== row.h_ini_partida,
    canviAula: row.aula !== row.aula_partida,
    recuperada,
  };
}

export function sessionsDeSetmana(
  db: Database,
  idVersio: number,
  setmana: string,
  dilluns: string,
  divendres: string,
  filtre: FiltreParrilla,
  limit: number,
): FranjaParrilla[] {
  const { sql, params } = clausesFiltre(filtre);
  const rows = db
    .prepare(`${SELECT_SESSIONS}${sql}${ORDRE_SQL} LIMIT @limit`)
    .all({ idVersio, setmana, dilluns, divendres, limit, ...params }) as SessioRow[];
  const ids = rows.map((r) => r.id_sessio);
  const profes = profesPerSessio(db, ids);
  const cohorts = cohortsPerSessio(db, ids);
  return rows.map((r) => aFranja(r, profes.get(r.id_sessio) ?? [], cohorts.get(r.id_sessio) ?? []));
}

export function calendariDeSetmana(db: Database, dilluns: string, divendres: string): DiaCalendari[] {
  const rows = db
    .prepare(
      `SELECT data, tipus, h_ini, h_fi, motiu FROM calendari
       WHERE data BETWEEN ? AND ? ORDER BY data, h_ini, id`,
    )
    .all(dilluns, divendres) as CalendariRow[];
  return rows.map((r) => ({ data: r.data, tipus: r.tipus, hIni: r.h_ini, hFi: r.h_fi, motiu: r.motiu }));
}
