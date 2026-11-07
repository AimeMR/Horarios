export type EstatRestriccio = "OK" | "KO" | "REL";

export interface RestriccioRecompte {
  regla: string;
  total: number;
  compten: number;
  declarades: number;
  heretades: number;
  estat: EstatRestriccio;
}

export interface NoAvaluable {
  regla: string;
  sessions: number;
}

export interface Objectius {
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
}

export interface ContextInforme {
  semestre: 1 | 2 | null;
  nomesAules: boolean;
}

export interface Informe {
  restriccions: RestriccioRecompte[];
  noAvaluables: NoAvaluable[];
  objectius: Objectius;
  relaxacionsDeclarades: number;
  incomplimentsDeclarats: number;
  context: ContextInforme;
}

export interface InformeVersio {
  idVersio: number;
  nom: string;
  veredicte: string | null;
  informe: Informe | null;
}

export function calcularEstat(compten: number, declarades: number): EstatRestriccio {
  if (compten > 0) return "KO";
  if (declarades > 0) return "REL";
  return "OK";
}
