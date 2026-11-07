import type { Database } from "better-sqlite3";
import type { AssignacioSetmana, AulaOcupacio, TipusAula } from "../../domain/ocupacio.js";

interface AulaRow {
  codi: string;
  edifici: string | null;
  tipus: TipusAula | null;
  capacitat: number | null;
  ordinaria: number;
}

interface AssignacioRow {
  aula: string;
  dia: AssignacioSetmana["dia"];
  h_ini: string;
  durada_min: number;
  data: string | null;
  data_partida: string;
  dia_partida: AssignacioSetmana["diaPartida"];
}

const AULES_SQL = `
  SELECT codi, edifici, tipus, capacitat, ordinaria
  FROM aula
  WHERE dins_aulari = 1 AND (@tipus IS NULL OR tipus = @tipus)
  ORDER BY codi ASC`;

const ORDINARIES_SQL = `
  SELECT codi, edifici, tipus, capacitat, ordinaria
  FROM aula
  WHERE ordinaria = 1 AND dins_aulari = 1
  ORDER BY codi ASC`;

const ASSIGNACIONS_SQL = `
  SELECT a.aula, a.dia, a.h_ini, s.durada_min, a.data, s.data_partida, s.dia_partida
  FROM assignacio a
  JOIN sessio s ON s.id_sessio = a.id_sessio
  WHERE a.id_versio = @idVersio
    AND a.aula IS NOT NULL
    AND ((a.data IS NULL AND s.setmana = @setmana) OR (a.data BETWEEN @dilluns AND @divendres))`;

function toAula(row: AulaRow): AulaOcupacio {
  return {
    codi: row.codi,
    edifici: row.edifici,
    tipus: row.tipus,
    capacitat: row.capacitat,
    ordinaria: row.ordinaria === 1,
  };
}

function toAssignacio(row: AssignacioRow): AssignacioSetmana {
  return {
    aula: row.aula,
    dia: row.dia,
    hIni: row.h_ini,
    duradaMin: row.durada_min,
    data: row.data,
    dataPartida: row.data_partida,
    diaPartida: row.dia_partida,
  };
}

export interface SetmanaConsulta {
  readonly idVersio: number;
  readonly setmana: string;
  readonly dilluns: string;
  readonly divendres: string;
}

export class OcupacioRepository {
  constructor(private readonly db: Database) {}

  versioExisteix(idVersio: number): boolean {
    const fila = this.db.prepare("SELECT 1 AS ok FROM versio_horari WHERE id_versio = ?").get(idVersio);
    return fila !== undefined;
  }

  aulesAulari(tipus: TipusAula | null): AulaOcupacio[] {
    return (this.db.prepare(AULES_SQL).all({ tipus }) as AulaRow[]).map(toAula);
  }

  aulesOrdinaries(): AulaOcupacio[] {
    return (this.db.prepare(ORDINARIES_SQL).all() as AulaRow[]).map(toAula);
  }

  assignacionsSetmana(consulta: SetmanaConsulta): AssignacioSetmana[] {
    const rows = this.db.prepare(ASSIGNACIONS_SQL).all({
      idVersio: consulta.idVersio,
      setmana: consulta.setmana,
      dilluns: consulta.dilluns,
      divendres: consulta.divendres,
    }) as AssignacioRow[];
    return rows.map(toAssignacio);
  }
}
