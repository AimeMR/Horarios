import { z } from "zod";
import { TIPUS_AULA, type Aula } from "../../domain/aula.js";
import { paginationSchema } from "../../http/pagination.js";

export const aulesQuerySchema = paginationSchema.extend({
  tipus: z.enum(TIPUS_AULA).optional(),
  capacitat_min: z
    .string()
    .regex(/^\d{1,4}$/)
    .transform(Number)
    .pipe(z.number().int().min(0).max(1000))
    .optional(),
});

export type AulesQuery = z.infer<typeof aulesQuerySchema>;

export type AulaDto = Aula;

export function toAulaDto(aula: Aula): AulaDto {
  return {
    codi: aula.codi,
    edifici: aula.edifici,
    espina: aula.espina,
    planta: aula.planta,
    tipus: aula.tipus,
    capacitat: aula.capacitat,
    ordinaria: aula.ordinaria,
    integrat: aula.integrat,
    nomesPlab: aula.nomesPlab,
    dinsAulari: aula.dinsAulari,
    admetNoves: aula.admetNoves,
    descripcio: aula.descripcio,
  };
}
