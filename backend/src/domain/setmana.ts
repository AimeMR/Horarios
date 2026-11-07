export const DIES = ["L", "M", "X", "J", "V"] as const;
export type Dia = (typeof DIES)[number];

const DIA_MS = 86_400_000;
const SETMANA_RE = /^(\d{4})-W(\d{2})$/;
const HORA_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;
const DATA_RE = /^\d{4}-\d{2}-\d{2}$/;

function isoData(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function msDeData(data: string): number {
  if (!DATA_RE.test(data)) {
    throw new RangeError("data no vàlida");
  }
  const ms = Date.parse(`${data}T00:00:00Z`);
  if (Number.isNaN(ms) || isoData(ms) !== data) {
    throw new RangeError("data no vàlida");
  }
  return ms;
}

/** Dilluns (AAAA-MM-DD) de la setmana ISO «AAAA-Www». Llança RangeError si la setmana no existeix. */
export function dillunsDeSetmana(setmana: string): string {
  const m = SETMANA_RE.exec(setmana);
  if (!m) {
    throw new RangeError("setmana no vàlida");
  }
  const any = Number(m[1]);
  const num = Number(m[2]);
  if (num < 1 || num > 53) {
    throw new RangeError("setmana no vàlida");
  }
  // El 4 de gener sempre és a la setmana 1 (ISO 8601).
  const quatreGener = Date.UTC(any, 0, 4);
  const diaSetmana = (new Date(quatreGener).getUTCDay() + 6) % 7; // 0 = dilluns
  const dilluns = quatreGener - diaSetmana * DIA_MS + (num - 1) * 7 * DIA_MS;
  // La setmana pertany a l'any del seu dijous: la W53 d'un any de 52 setmanes cau a l'any següent.
  if (new Date(dilluns + 3 * DIA_MS).getUTCFullYear() !== any) {
    throw new RangeError("setmana no vàlida");
  }
  return isoData(dilluns);
}

/** Les cinc dates lectives (dilluns a divendres) de la setmana. */
export function diesDeSetmana(setmana: string): ReadonlyArray<{ dia: Dia; data: string }> {
  const dilluns = msDeData(dillunsDeSetmana(setmana));
  return DIES.map((dia, i) => ({ dia, data: isoData(dilluns + i * DIA_MS) }));
}

/** Data del dia `dia` dins la mateixa setmana ISO que `dataPartida` (que cau en `diaPartida`). */
export function dataMateixaSetmana(dataPartida: string, diaPartida: Dia, dia: Dia): string {
  const desplacament = DIES.indexOf(dia) - DIES.indexOf(diaPartida);
  return isoData(msDeData(dataPartida) + desplacament * DIA_MS);
}

/** «HH:MM» -> minuts des de mitjanit. */
export function minuts(hora: string): number {
  const m = HORA_RE.exec(hora);
  if (!m) {
    throw new RangeError("hora no vàlida");
  }
  return Number(m[1]) * 60 + Number(m[2]);
}

/** Minuts des de mitjanit -> «HH:MM» (0..1439). */
export function hora(totalMinuts: number): string {
  if (!Number.isInteger(totalMinuts) || totalMinuts < 0 || totalMinuts >= 24 * 60) {
    throw new RangeError("minuts fora de rang");
  }
  const h = Math.floor(totalMinuts / 60);
  const m = totalMinuts % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
