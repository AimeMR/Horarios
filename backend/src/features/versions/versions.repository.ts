import type { Database } from "better-sqlite3";
import type { Assignacio } from "../../domain/assignacio.js";
import type { Versio } from "../../domain/versio.js";

interface VersioRow {
  id_versio: number;
  nom: string;
  id_versio_referencia: number | null;
  id_escenari: string | null;
  semestre: 1 | 2 | null;
  mode: Versio["mode"];
  creada_el: string;
  veredicte: Versio["veredicte"];
}

interface AssignacioRow {
  id_sessio: string;
  dia: Assignacio["dia"];
  h_ini: string;
  aula: string | null;
  data: string | null;
}

interface CountRow {
  total: number;
}

export interface VersionsRepository {
  listVersions(limit: number, offset: number): Versio[];
  countVersions(): number;
  versioExists(id: number): boolean;
  listAssignacions(id: number, limit: number, offset: number): Assignacio[];
  countAssignacions(id: number): number;
}

function toVersio(row: VersioRow): Versio {
  return {
    id: row.id_versio,
    nom: row.nom,
    idVersioReferencia: row.id_versio_referencia,
    idEscenari: row.id_escenari,
    semestre: row.semestre,
    mode: row.mode,
    creadaEl: row.creada_el,
    veredicte: row.veredicte,
  };
}

function toAssignacio(row: AssignacioRow): Assignacio {
  return { idSessio: row.id_sessio, dia: row.dia, hIni: row.h_ini, aula: row.aula, data: row.data };
}

export function createVersionsRepository(db: Database): VersionsRepository {
  return {
    listVersions(limit, offset) {
      const rows = db
        .prepare(
          `SELECT id_versio, nom, id_versio_referencia, id_escenari, semestre, mode, creada_el, veredicte
           FROM versio_horari ORDER BY id_versio ASC LIMIT ? OFFSET ?`,
        )
        .all(limit, offset) as VersioRow[];
      return rows.map(toVersio);
    },
    countVersions() {
      const row = db.prepare("SELECT COUNT(*) AS total FROM versio_horari").get() as CountRow;
      return row.total;
    },
    versioExists(id) {
      return db.prepare("SELECT 1 FROM versio_horari WHERE id_versio = ?").get(id) !== undefined;
    },
    listAssignacions(id, limit, offset) {
      const rows = db
        .prepare(
          `SELECT id_sessio, dia, h_ini, aula, data FROM assignacio
           WHERE id_versio = ? ORDER BY id_sessio ASC LIMIT ? OFFSET ?`,
        )
        .all(id, limit, offset) as AssignacioRow[];
      return rows.map(toAssignacio);
    },
    countAssignacions(id) {
      const row = db.prepare("SELECT COUNT(*) AS total FROM assignacio WHERE id_versio = ?").get(id) as CountRow;
      return row.total;
    },
  };
}
