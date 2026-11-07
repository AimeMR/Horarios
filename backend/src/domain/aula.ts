export const TIPUS_AULA = ["Aules docents", "Laboratoris docents", "Seminaris", "Aules informàtiques"] as const;

export type TipusAula = (typeof TIPUS_AULA)[number];

export interface Aula {
  codi: string;
  edifici: string | null;
  espina: string;
  planta: number;
  tipus: TipusAula | null;
  capacitat: number | null;
  ordinaria: boolean;
  integrat: boolean;
  nomesPlab: boolean;
  dinsAulari: boolean;
  admetNoves: boolean;
  descripcio: string | null;
}
