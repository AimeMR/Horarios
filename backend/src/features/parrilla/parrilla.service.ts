import type { Database } from "better-sqlite3";
import { NotFoundError } from "../../domain/errors.js";
import type { ConsultaParrilla, FranjaParrilla, Parrilla } from "../../domain/parrilla.js";
import { diesDeSetmana } from "../../domain/setmana.js";
import { calendariDeSetmana, sessionsDeSetmana, versioExisteix } from "./parrilla.repository.js";

export const MAX_ITEMS = 1000;

function compara(a: string, b: string): number {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

function comparaAula(a: string | null, b: string | null): number {
  if (a === b) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return compara(a, b);
}

function comparaFranges(a: FranjaParrilla, b: FranjaParrilla): number {
  return (
    compara(a.data, b.data) ||
    compara(a.hIni, b.hIni) ||
    comparaAula(a.aula, b.aula) ||
    compara(a.idSessio, b.idSessio)
  );
}

export function consultarParrilla(db: Database, idVersio: number, consulta: ConsultaParrilla): Parrilla {
  if (!versioExisteix(db, idVersio)) {
    throw new NotFoundError("versió inexistent");
  }
  const dies = diesDeSetmana(consulta.setmana);
  const dilluns = dies[0]?.data;
  const divendres = dies[4]?.data;
  if (dilluns === undefined || divendres === undefined) {
    throw new RangeError("setmana sense dies");
  }
  const sessions = sessionsDeSetmana(db, idVersio, consulta.setmana, dilluns, divendres, consulta.filtre);
  const ordenades = [...sessions].sort(comparaFranges);
  return {
    idVersio,
    setmana: consulta.setmana,
    dies,
    filtre: consulta.filtre,
    calendari: calendariDeSetmana(db, dilluns, divendres),
    items: ordenades.slice(0, MAX_ITEMS),
    truncat: ordenades.length > MAX_ITEMS,
  };
}
