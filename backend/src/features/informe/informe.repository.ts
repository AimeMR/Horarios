import type { Database } from "better-sqlite3";

export interface VersioInformeRow {
  id_versio: number;
  nom: string;
  veredicte: string | null;
  informe_json: string | null;
}

export function findVersioInforme(db: Database, idVersio: number): VersioInformeRow | undefined {
  return db
    .prepare("SELECT id_versio, nom, veredicte, informe_json FROM versio_horari WHERE id_versio = ?")
    .get(idVersio) as VersioInformeRow | undefined;
}
