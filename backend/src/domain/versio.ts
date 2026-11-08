export type VeredicteVersio = "VALIDA" | "VALIDA AMB RELAXACIONS DECLARADES" | "NO VALIDA";

export interface Versio {
  id: number;
  nom: string;
  idVersioReferencia: number | null;
  idEscenari: string | null;
  semestre: 1 | 2 | null;
  mode: "complet" | "nomes_aules";
  creadaEl: string;
  veredicte: VeredicteVersio | null;
}
