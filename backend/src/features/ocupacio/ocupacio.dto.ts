import { z } from "zod";
import { TIPUS_AULA } from "../../domain/aula.js";
import type { Ocupacio } from "../../domain/ocupacio.js";
import { setmanaExistentSchema } from "../../http/params.js";

export const ocupacioQuerySchema = z.object({
  setmana: setmanaExistentSchema,
  tipus: z.enum(TIPUS_AULA).optional(),
});

export type OcupacioQueryDto = z.infer<typeof ocupacioQuerySchema>;

export interface OcupacioDto {
  idVersio: number;
  setmana: string;
  dies: Array<{ dia: string; data: string }>;
  franges: string[];
  perAula: Array<{
    codi: string;
    edifici: string | null;
    tipus: string | null;
    capacitat: number | null;
    ordinaria: boolean;
    sessions: number;
    minutsOcupats: number;
    minutsDisponibles: number;
    percentatge: number;
  }>;
  perFranja: Array<{
    dia: string;
    data: string;
    franja: string;
    ocupades: number;
    lliures: number;
    ordinariesLliures: number;
    reservaOk: boolean;
  }>;
}

export function toOcupacioDto(o: Ocupacio): OcupacioDto {
  return {
    idVersio: o.idVersio,
    setmana: o.setmana,
    dies: o.dies.map((d) => ({ dia: d.dia, data: d.data })),
    franges: [...o.franges],
    perAula: o.perAula.map((a) => ({
      codi: a.codi,
      edifici: a.edifici,
      tipus: a.tipus,
      capacitat: a.capacitat,
      ordinaria: a.ordinaria,
      sessions: a.sessions,
      minutsOcupats: a.minutsOcupats,
      minutsDisponibles: a.minutsDisponibles,
      percentatge: a.percentatge,
    })),
    perFranja: o.perFranja.map((f) => ({
      dia: f.dia,
      data: f.data,
      franja: f.franja,
      ocupades: f.ocupades,
      lliures: f.lliures,
      ordinariesLliures: f.ordinariesLliures,
      reservaOk: f.reservaOk,
    })),
  };
}
