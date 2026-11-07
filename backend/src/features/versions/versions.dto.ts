import type { Assignacio } from "../../domain/assignacio.js";
import type { Versio } from "../../domain/versio.js";
import { paginationSchema } from "../../http/pagination.js";

export const versionsQuerySchema = paginationSchema;

export type VersioDto = Versio;
export type AssignacioDto = Assignacio;

export function toVersioDto(v: Versio): VersioDto {
  return {
    id: v.id,
    nom: v.nom,
    idVersioReferencia: v.idVersioReferencia,
    idEscenari: v.idEscenari,
    semestre: v.semestre,
    mode: v.mode,
    creadaEl: v.creadaEl,
    veredicte: v.veredicte,
  };
}

export function toAssignacioDto(a: Assignacio): AssignacioDto {
  return { idSessio: a.idSessio, dia: a.dia, hIni: a.hIni, aula: a.aula, data: a.data };
}
