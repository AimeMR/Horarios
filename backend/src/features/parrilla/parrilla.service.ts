import type { Database } from "better-sqlite3";
import { NotFoundError } from "../../domain/errors.js";
import type { ConsultaParrilla, Parrilla } from "../../domain/parrilla.js";
import { diesDeSetmana } from "../../domain/setmana.js";
import { calendariDeSetmana, sessionsDeSetmana, versioExisteix } from "./parrilla.repository.js";

export const MAX_ITEMS = 1000;

export function consultarParrilla(
  db: Database,
  idVersio: number,
  consulta: ConsultaParrilla,
  maxItems: number = MAX_ITEMS,
): Parrilla {
  if (!versioExisteix(db, idVersio)) {
    throw new NotFoundError("versió inexistent");
  }
  const dies = diesDeSetmana(consulta.setmana);
  const dilluns = dies[0]?.data;
  const divendres = dies[4]?.data;
  if (dilluns === undefined || divendres === undefined) {
    throw new RangeError("setmana sense dies");
  }
  // Una fila de més, ordenada ja a SQL, només per saber si s'ha truncat.
  const sessions = sessionsDeSetmana(db, idVersio, consulta.setmana, dilluns, divendres, consulta.filtre, maxItems + 1);
  return {
    idVersio,
    setmana: consulta.setmana,
    dies,
    filtre: consulta.filtre,
    calendari: calendariDeSetmana(db, dilluns, divendres),
    items: sessions.slice(0, maxItems),
    truncat: sessions.length > maxItems,
  };
}
