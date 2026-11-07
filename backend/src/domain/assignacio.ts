export interface Assignacio {
  idSessio: string;
  dia: "L" | "M" | "X" | "J" | "V";
  hIni: string;
  aula: string | null;
  data: string | null;
}
