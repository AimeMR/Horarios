import type { TipusAula } from "./aula.js";
import { type Dia, hora } from "./setmana.js";

/** Interval semiobert [ini, fi) en minuts des de mitjanit. */
export interface Interval {
  readonly ini: number;
  readonly fi: number;
}

export interface Franja extends Interval {
  readonly hora: string;
}

export const FINESTRA: Interval = { ini: 8 * 60 + 30, fi: 21 * 60 };
export const MINUTS_DIA = FINESTRA.fi - FINESTRA.ini;
export const MINUTS_SETMANA = MINUTS_DIA * 5;

const NUM_FRANGES = 13;
const DURADA_FRANJA = 60;

/** Les 13 franges: inicis 08:30..20:30; cadascuna dura 60 min i la darrera acaba a les 21:00. */
export function franges(): ReadonlyArray<Franja> {
  return Array.from({ length: NUM_FRANGES }, (_, i) => {
    const ini = FINESTRA.ini + i * DURADA_FRANJA;
    return { hora: hora(ini), ini, fi: Math.min(ini + DURADA_FRANJA, FINESTRA.fi) };
  });
}

/** Dos intervals semioberts es solapen si cadascun comença abans que l'altre acabi. */
export function solapa(a: Interval, b: Interval): boolean {
  return a.ini < b.fi && b.ini < a.fi;
}

/** Minuts coberts per la unió dels intervals, retallats a la finestra diària. */
export function minutsUnio(intervals: ReadonlyArray<Interval>): number {
  const retallats = intervals
    .map((i) => ({ ini: Math.max(i.ini, FINESTRA.ini), fi: Math.min(i.fi, FINESTRA.fi) }))
    .filter((i) => i.ini < i.fi)
    .sort((a, b) => a.ini - b.ini);
  let total = 0;
  let fins = -Infinity;
  for (const { ini, fi } of retallats) {
    const inici = Math.max(ini, fins);
    if (fi > inici) {
      total += fi - inici;
    }
    fins = Math.max(fins, fi);
  }
  return total;
}

/** Percentatge amb un decimal. */
export function percentatge(ocupats: number, disponibles: number): number {
  return Math.round((1000 * ocupats) / disponibles) / 10;
}

export interface AulaOcupacio {
  readonly codi: string;
  readonly edifici: string | null;
  readonly tipus: TipusAula | null;
  readonly capacitat: number | null;
  readonly ordinaria: boolean;
}

export interface AssignacioSetmana {
  readonly aula: string;
  readonly dia: Dia;
  readonly hIni: string;
  readonly duradaMin: number;
  readonly data: string | null;
  readonly dataPartida: string;
  readonly diaPartida: Dia;
}

export interface OcupacioAula extends AulaOcupacio {
  readonly sessions: number;
  readonly minutsOcupats: number;
  readonly minutsDisponibles: number;
  readonly percentatge: number;
}

export interface OcupacioFranja {
  readonly dia: Dia;
  readonly data: string;
  readonly franja: string;
  readonly ocupades: number;
  readonly lliures: number;
  readonly ordinariesLliures: number;
  readonly reservaOk: boolean;
}

export interface Ocupacio {
  readonly idVersio: number;
  readonly setmana: string;
  readonly dies: ReadonlyArray<{ dia: Dia; data: string }>;
  readonly franges: ReadonlyArray<string>;
  readonly perAula: ReadonlyArray<OcupacioAula>;
  readonly perFranja: ReadonlyArray<OcupacioFranja>;
}
