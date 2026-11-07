import type { Dia } from "./setmana.js";

export interface FiltreParrilla {
  readonly aula?: string | undefined;
  readonly cohort?: string | undefined;
  readonly profe?: string | undefined;
  readonly assignatura?: string | undefined;
  readonly grup?: string | undefined;
}

export interface ConsultaParrilla {
  readonly setmana: string;
  readonly filtre: FiltreParrilla;
}

export interface FranjaParrilla {
  readonly idSessio: string;
  readonly data: string;
  readonly dia: Dia;
  readonly hIni: string;
  readonly hFi: string;
  readonly duradaMin: number;
  readonly aula: string | null;
  readonly assignatura: { readonly codi: string; readonly nom: string };
  readonly grup: { readonly idGrup: string; readonly grup: string; readonly tipus: string };
  readonly alumnes: number;
  readonly profes: readonly string[];
  readonly cohorts: readonly string[];
  readonly idCompartida: string | null;
  readonly fixadaMotiu: string | null;
  readonly moguda: boolean;
  readonly canviAula: boolean;
  readonly recuperada: boolean;
}

export interface DiaCalendari {
  readonly data: string;
  readonly tipus: string;
  readonly hIni: string | null;
  readonly hFi: string | null;
  readonly motiu: string;
}

export interface Parrilla {
  readonly idVersio: number;
  readonly setmana: string;
  readonly dies: ReadonlyArray<{ readonly dia: Dia; readonly data: string }>;
  readonly filtre: FiltreParrilla;
  readonly calendari: readonly DiaCalendari[];
  readonly items: readonly FranjaParrilla[];
  readonly truncat: boolean;
}
