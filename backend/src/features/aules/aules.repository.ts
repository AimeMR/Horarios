import type { Database } from "better-sqlite3";
import type { Aula, TipusAula } from "../../domain/aula.js";

export interface AulaFilters {
  tipus?: TipusAula | undefined;
  capacitatMin?: number | undefined;
  limit: number;
  offset: number;
}

interface AulaRow {
  codi: string;
  edifici: string | null;
  espina: string;
  planta: number;
  tipus: TipusAula | null;
  capacitat: number | null;
  ordinaria: number;
  integrat: number;
  nomes_plab: number;
  dins_aulari: number;
  admet_noves: number;
  descripcio: string | null;
}

const COLUMNS =
  "codi, edifici, espina, planta, tipus, capacitat, ordinaria, integrat, nomes_plab, dins_aulari, admet_noves, descripcio";

function toAula(row: AulaRow): Aula {
  return {
    codi: row.codi,
    edifici: row.edifici,
    espina: row.espina,
    planta: row.planta,
    tipus: row.tipus,
    capacitat: row.capacitat,
    ordinaria: row.ordinaria === 1,
    integrat: row.integrat === 1,
    nomesPlab: row.nomes_plab === 1,
    dinsAulari: row.dins_aulari === 1,
    admetNoves: row.admet_noves === 1,
    descripcio: row.descripcio,
  };
}

export function createAulesRepository(db: Database) {
  return {
    list(filters: AulaFilters): { items: Aula[]; total: number } {
      const conditions: string[] = [];
      const params: (string | number)[] = [];
      if (filters.tipus !== undefined) {
        conditions.push("tipus = ?");
        params.push(filters.tipus);
      }
      if (filters.capacitatMin !== undefined) {
        conditions.push("capacitat >= ?");
        params.push(filters.capacitatMin);
      }
      const where = conditions.length > 0 ? ` WHERE ${conditions.join(" AND ")}` : "";
      const totalRow = db.prepare(`SELECT COUNT(*) AS total FROM aula${where}`).get(...params) as { total: number };
      const rows = db
        .prepare(`SELECT ${COLUMNS} FROM aula${where} ORDER BY codi ASC LIMIT ? OFFSET ?`)
        .all(...params, filters.limit, filters.offset) as AulaRow[];
      return { items: rows.map(toAula), total: totalRow.total };
    },
  };
}

export type AulesRepository = ReturnType<typeof createAulesRepository>;
