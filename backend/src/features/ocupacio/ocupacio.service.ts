import { NotFoundError } from "../../domain/errors.js";
import {
  MINUTS_SETMANA,
  franges,
  minutsUnio,
  percentatge,
  solapa,
  type AssignacioSetmana,
  type AulaOcupacio,
  type Franja,
  type Interval,
  type Ocupacio,
  type OcupacioAula,
  type OcupacioFranja,
  type TipusAula,
} from "../../domain/ocupacio.js";
import { dataMateixaSetmana, diesDeSetmana, minuts } from "../../domain/setmana.js";
import type { OcupacioRepository } from "./ocupacio.repository.js";

type Dies = ReturnType<typeof diesDeSetmana>;
type Dia = Dies[number];
/** Intervals ocupats per aula i data efectiva. */
type Ocupades = Map<string, Map<string, Interval[]>>;

export interface OcupacioQuery {
  readonly setmana: string;
  readonly tipus: TipusAula | undefined;
}

function dataEfectiva(a: AssignacioSetmana): string {
  return a.data ?? dataMateixaSetmana(a.dataPartida, a.diaPartida, a.dia);
}

function intervalDe(a: AssignacioSetmana): Interval {
  const ini = minuts(a.hIni);
  return { ini, fi: ini + a.duradaMin };
}

function agrupa(assignacions: ReadonlyArray<AssignacioSetmana>): Ocupades {
  const perAula: Ocupades = new Map();
  for (const a of assignacions) {
    const perData = perAula.get(a.aula) ?? new Map<string, Interval[]>();
    const data = dataEfectiva(a);
    perData.set(data, [...(perData.get(data) ?? []), intervalDe(a)]);
    perAula.set(a.aula, perData);
  }
  return perAula;
}

function ocupadaEn(ocupades: Ocupades, codi: string, data: string, franja: Interval): boolean {
  return (ocupades.get(codi)?.get(data) ?? []).some((i) => solapa(i, franja));
}

function calculaPerAula(
  aules: ReadonlyArray<AulaOcupacio>,
  assignacions: ReadonlyArray<AssignacioSetmana>,
  ocupades: Ocupades,
): OcupacioAula[] {
  return aules.map((aula) => {
    const sessions = assignacions.filter((a) => a.aula === aula.codi).length;
    let minutsOcupats = 0;
    for (const intervals of ocupades.get(aula.codi)?.values() ?? []) {
      minutsOcupats += minutsUnio(intervals);
    }
    return {
      ...aula,
      sessions,
      minutsOcupats,
      minutsDisponibles: MINUTS_SETMANA,
      percentatge: percentatge(minutsOcupats, MINUTS_SETMANA),
    };
  });
}

interface ConjuntsFranja {
  readonly considerades: ReadonlyArray<AulaOcupacio>;
  readonly ordinaries: ReadonlyArray<AulaOcupacio>;
  readonly ocupadesConsiderades: Ocupades;
  readonly ocupadesTotes: Ocupades;
}

function calculaFranja(dia: Dia, franja: Franja, c: ConjuntsFranja): OcupacioFranja {
  const ocupades = c.considerades.filter((a) => ocupadaEn(c.ocupadesConsiderades, a.codi, dia.data, franja)).length;
  const ordinariesLliures = c.ordinaries.filter((a) => !ocupadaEn(c.ocupadesTotes, a.codi, dia.data, franja)).length;
  return {
    dia: dia.dia,
    data: dia.data,
    franja: franja.hora,
    ocupades,
    lliures: c.considerades.length - ocupades,
    ordinariesLliures,
    reservaOk: ordinariesLliures >= 2,
  };
}

export class OcupacioService {
  constructor(private readonly repo: OcupacioRepository) {}

  calcula(idVersio: number, query: OcupacioQuery): Ocupacio {
    if (!this.repo.versioExisteix(idVersio)) {
      throw new NotFoundError("versio inexistent");
    }
    const dies = diesDeSetmana(query.setmana);
    const primera = dies[0];
    const darrera = dies[dies.length - 1];
    if (!primera || !darrera) {
      throw new RangeError("setmana sense dies");
    }
    const considerades = this.repo.aulesAulari(query.tipus ?? null);
    const ordinaries = this.repo.aulesOrdinaries();
    const totes = this.repo.assignacionsSetmana({
      idVersio,
      setmana: query.setmana,
      dilluns: primera.data,
      divendres: darrera.data,
    });
    const codis = new Set(considerades.map((a) => a.codi));
    const assignacions = totes.filter((a) => codis.has(a.aula));
    const ocupadesConsiderades = agrupa(assignacions);
    const conjunts: ConjuntsFranja = {
      considerades,
      ordinaries,
      ocupadesConsiderades,
      ocupadesTotes: agrupa(totes),
    };
    const llistaFranges = franges();
    return {
      idVersio,
      setmana: query.setmana,
      dies: dies.map((d) => ({ dia: d.dia, data: d.data })),
      franges: llistaFranges.map((f) => f.hora),
      perAula: calculaPerAula(considerades, assignacions, ocupadesConsiderades),
      perFranja: dies.flatMap((dia) => llistaFranges.map((franja) => calculaFranja(dia, franja, conjunts))),
    };
  }
}
