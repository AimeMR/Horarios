import type { Database } from "better-sqlite3";
import { NotFoundError } from "../../domain/errors.js";
import { calcularEstat, type Informe, type InformeVersio, type RestriccioRecompte } from "../../domain/informe.js";
import { REGLES, informeGuardatSchema, type InformeGuardat } from "./informe.dto.js";
import { findVersioInforme } from "./informe.repository.js";

function parseGuardat(json: string): InformeGuardat {
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    throw new Error("informe_json no es JSON valido");
  }
  const result = informeGuardatSchema.safeParse(raw);
  if (!result.success) throw new Error("informe_json no cumple el esquema");
  return result.data;
}

function restriccio(
  regla: string,
  c: { total: number; compten: number; declarades: number; heretades: number } | undefined,
): RestriccioRecompte {
  const total = c?.total ?? 0;
  const compten = c?.compten ?? 0;
  const declarades = c?.declarades ?? 0;
  const heretades = c?.heretades ?? 0;
  return { regla, total, compten, declarades, heretades, estat: calcularEstat(compten, declarades) };
}

function buildRestriccions(guardades: InformeGuardat["restriccions"]): RestriccioRecompte[] {
  const perRegla = new Map(Object.entries(guardades));
  const conegudes = new Set<string>(REGLES);
  const desconegudes = [...perRegla.keys()].filter((r) => !conegudes.has(r)).sort();
  return [...REGLES, ...desconegudes].map((regla) => restriccio(regla, perRegla.get(regla)));
}

function buildInforme(g: InformeGuardat): Informe {
  const o = g.objectius;
  return {
    restriccions: buildRestriccions(g.restriccions),
    noAvaluables: Object.entries(g.no_avaluables)
      .map(([regla, sessions]) => ({ regla, sessions }))
      .sort((a, b) => (a.regla < b.regla ? -1 : a.regla > b.regla ? 1 : 0)),
    objectius: {
      horesMortesMin: o.hores_mortes_min,
      desplacamentsAula: o.desplacaments_aula,
      desplacamentsEdifici: o.desplacaments_edifici,
      canvisFranja: o.canvis_franja,
      canvisAula: o.canvis_aula,
      r6AulesTeExtraPerGrup: o.r6_aules_te_extra_per_grup,
      r6CanvisTePaulForaPassadis: o.r6_canvis_te_paul_fora_passadis,
      sessionsAvaluades: o.sessions_avaluades,
      canvisFranjaVsReferencia: o.canvis_franja_vs_referencia ?? null,
      canvisAulaVsReferencia: o.canvis_aula_vs_referencia ?? null,
    },
    relaxacionsDeclarades: g.relaxacions_declarades,
    incomplimentsDeclarats: g.incompliments_declarats,
    context: { semestre: g.context.semestre, nomesAules: g.context.nomes_aules },
  };
}

export function getInforme(db: Database, idVersio: number): InformeVersio {
  const row = findVersioInforme(db, idVersio);
  if (row === undefined) throw new NotFoundError("version no encontrada");
  return {
    idVersio: row.id_versio,
    nom: row.nom,
    veredicte: row.veredicte,
    informe: row.informe_json === null ? null : buildInforme(parseGuardat(row.informe_json)),
  };
}
