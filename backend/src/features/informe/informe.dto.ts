import { z } from "zod";
import type { Informe, InformeVersio } from "../../domain/informe.js";

export const REGLES = [
  "R0-FORMAT",
  "R0-HORARI",
  "R1-FIXADA",
  "R1-TORN",
  "R2-FINESTRA",
  "R2-CALENDARI",
  "R3-AULA",
  "R3-AFORAMENT",
  "R3-TIPUS",
  "R3-TANCADA",
  "R4-AULA",
  "R4-DOCENT",
  "R4-ALUMNAT",
  "R4-PLAB",
  "R4-COMPARTIDA",
  "R5-FALTA",
  "R5-SENSE-AULA",
  "R5-RECUPERACIO",
  "R7-PLAB",
  "R8-RESERVA",
] as const;

const recompte = z.number().finite().nonnegative();

const MAX_REGLES = 100;
const clauRegla = z.string().regex(/^R\d{1,2}-[A-Z0-9-]{1,32}$/);

function mapaDeRegles<T extends z.ZodType>(valor: T) {
  return z
    .record(clauRegla, valor)
    .refine((mapa) => Object.keys(mapa).length <= MAX_REGLES, { message: "massa regles" });
}

export const informeGuardatSchema = z.object({
  restriccions: mapaDeRegles(
    z.object({ total: recompte, compten: recompte, declarades: recompte, heretades: recompte }),
  ),
  no_avaluables: mapaDeRegles(recompte),
  objectius: z.object({
    hores_mortes_min: recompte,
    desplacaments_aula: recompte,
    desplacaments_edifici: recompte,
    canvis_franja: recompte,
    canvis_aula: recompte,
    r6_aules_te_extra_per_grup: recompte,
    r6_canvis_te_paul_fora_passadis: recompte,
    sessions_avaluades: recompte,
    canvis_franja_vs_referencia: recompte.optional(),
    canvis_aula_vs_referencia: recompte.optional(),
  }),
  relaxacions_declarades: recompte,
  incompliments_declarats: recompte,
  context: z.object({
    semestre: z.union([z.literal(1), z.literal(2), z.null()]),
    nomes_aules: z.boolean(),
  }),
});

export type InformeGuardat = z.infer<typeof informeGuardatSchema>;

export interface RestriccioDto {
  regla: string;
  total: number;
  compten: number;
  declarades: number;
  heretades: number;
  estat: "OK" | "KO" | "REL";
}

export interface InformeDto {
  restriccions: RestriccioDto[];
  noAvaluables: { regla: string; sessions: number }[];
  objectius: {
    horesMortesMin: number;
    desplacamentsAula: number;
    desplacamentsEdifici: number;
    canvisFranja: number;
    canvisAula: number;
    r6AulesTeExtraPerGrup: number;
    r6CanvisTePaulForaPassadis: number;
    sessionsAvaluades: number;
    canvisFranjaVsReferencia: number | null;
    canvisAulaVsReferencia: number | null;
  };
  relaxacionsDeclarades: number;
  incomplimentsDeclarats: number;
  context: { semestre: 1 | 2 | null; nomesAules: boolean };
}

export interface InformeVersioDto {
  idVersio: number;
  nom: string;
  veredicte: string | null;
  informe: InformeDto | null;
}

function toInformeDto(informe: Informe): InformeDto {
  return {
    restriccions: informe.restriccions.map((r) => ({
      regla: r.regla,
      total: r.total,
      compten: r.compten,
      declarades: r.declarades,
      heretades: r.heretades,
      estat: r.estat,
    })),
    noAvaluables: informe.noAvaluables.map((n) => ({ regla: n.regla, sessions: n.sessions })),
    objectius: { ...informe.objectius },
    relaxacionsDeclarades: informe.relaxacionsDeclarades,
    incomplimentsDeclarats: informe.incomplimentsDeclarats,
    context: { semestre: informe.context.semestre, nomesAules: informe.context.nomesAules },
  };
}

export function toInformeVersioDto(v: InformeVersio): InformeVersioDto {
  return {
    idVersio: v.idVersio,
    nom: v.nom,
    veredicte: v.veredicte,
    informe: v.informe === null ? null : toInformeDto(v.informe),
  };
}
