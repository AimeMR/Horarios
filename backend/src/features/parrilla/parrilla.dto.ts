import { z } from "zod";
import type { ConsultaParrilla, FiltreParrilla, Parrilla } from "../../domain/parrilla.js";
import { setmanaExistentSchema } from "../../http/params.js";

export const parrillaQuerySchema = z
  .object({
    setmana: setmanaExistentSchema,
    aula: z
      .string()
      .regex(/^[A-Za-z0-9]{1,8}\/[A-Za-z0-9]{1,8}$/)
      .optional(),
    cohort: z
      .string()
      .regex(/^[A-Za-z0-9]{1,12}:(1r|2n|3r|4t|M|\?)$/)
      .optional(),
    profe: z
      .string()
      .regex(/^[A-Za-z0-9]{1,12}$/)
      .optional(),
    assignatura: z
      .string()
      .regex(/^[0-9]{1,12}$/)
      .optional(),
    grup: z
      .string()
      .regex(/^[0-9]{1,12}·(TE|PAUL|PLAB|SEM)\/[0-9]{1,6}$/)
      .optional(),
  })
  .superRefine((q, ctx) => {
    if ([q.aula, q.cohort, q.profe, q.assignatura, q.grup].every((v) => v === undefined)) {
      ctx.addIssue({ code: "custom", message: "cal almenys un filtre", path: ["filtre"] });
    }
  })
  .transform(
    (q): ConsultaParrilla => ({
      setmana: q.setmana,
      filtre: {
        ...(q.aula !== undefined && { aula: q.aula }),
        ...(q.cohort !== undefined && { cohort: q.cohort }),
        ...(q.profe !== undefined && { profe: q.profe }),
        ...(q.assignatura !== undefined && { assignatura: q.assignatura }),
        ...(q.grup !== undefined && { grup: q.grup }),
      } satisfies FiltreParrilla,
    }),
  );

export interface ParrillaDto {
  idVersio: number;
  setmana: string;
  dies: Array<{ dia: string; data: string }>;
  filtre: FiltreParrilla;
  calendari: Array<{ data: string; tipus: string; hIni: string | null; hFi: string | null; motiu: string }>;
  items: Array<{
    idSessio: string;
    data: string;
    dia: string;
    hIni: string;
    hFi: string;
    duradaMin: number;
    aula: string | null;
    assignatura: { codi: string; nom: string };
    grup: { idGrup: string; grup: string; tipus: string };
    alumnes: number;
    profes: string[];
    cohorts: string[];
    idCompartida: string | null;
    fixadaMotiu: string | null;
    moguda: boolean;
    canviAula: boolean;
    recuperada: boolean;
  }>;
  truncat: boolean;
}

export function toParrillaDto(p: Parrilla): ParrillaDto {
  return {
    idVersio: p.idVersio,
    setmana: p.setmana,
    dies: p.dies.map((d) => ({ dia: d.dia, data: d.data })),
    filtre: p.filtre,
    calendari: p.calendari.map((c) => ({ ...c })),
    items: p.items.map((i) => ({
      idSessio: i.idSessio,
      data: i.data,
      dia: i.dia,
      hIni: i.hIni,
      hFi: i.hFi,
      duradaMin: i.duradaMin,
      aula: i.aula,
      assignatura: { ...i.assignatura },
      grup: { ...i.grup },
      alumnes: i.alumnes,
      profes: [...i.profes],
      cohorts: [...i.cohorts],
      idCompartida: i.idCompartida,
      fixadaMotiu: i.fixadaMotiu,
      moguda: i.moguda,
      canviAula: i.canviAula,
      recuperada: i.recuperada,
    })),
    truncat: p.truncat,
  };
}
