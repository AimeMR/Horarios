import express from "express";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openWritableCopy, testDeps } from "../../../test/helpers.js";
import type { AppDeps } from "../../http/app.js";
import { errorHandler, notFoundHandler } from "../../http/errors.js";
import { ocupacioRouter } from "./ocupacio.controller.js";

// Valors derivats de tests/fixtures/paquet_fals (aules.csv, sessions.csv, proposta_partida.csv).
// Setmana 2026-W38 = 2026-09-14 (L) .. 2026-09-18 (V). Aules dins_aulari=1 (7), ordenades per codi:
// Q5/5105, Q7/7101, Q7/7102, Q7/7204, Q8/8103, Q8/8206, Q8/8307. Ordinaries: Q7/7101, Q7/7102, Q8/8103.
// Sessions de la W38 amb aula dins de l'aulari (durades de 90 min):
//   Q8/8103: S90005 L 08:30, S90013 M 08:30, S90019 J 12:00  -> 3 sessions, 270 min
//   Q7/7101: S90001 X 10:00, S90003 V 09:00, S90015 J 08:30  -> 3 sessions, 270 min
//   Q7/7204: S90009 X 08:30                                  -> 1 sessio, 90 min
//   S90017 (X 12:00) es a J/012 (externa, dins_aulari = 0): no compta mai.

interface AulaBody {
  codi: string;
  edifici: string;
  tipus: string;
  capacitat: number;
  ordinaria: boolean;
  sessions: number;
  minutsOcupats: number;
  minutsDisponibles: number;
  percentatge: number;
}

interface FranjaBody {
  dia: string;
  data: string;
  franja: string;
  ocupades: number;
  lliures: number;
  ordinariesLliures: number;
  reservaOk: boolean;
}

interface OcupacioBody {
  idVersio: number;
  setmana: string;
  dies: Array<{ dia: string; data: string }>;
  franges: string[];
  perAula: AulaBody[];
  perFranja: FranjaBody[];
}

const FRANGES = [
  "08:30",
  "09:30",
  "10:30",
  "11:30",
  "12:30",
  "13:30",
  "14:30",
  "15:30",
  "16:30",
  "17:30",
  "18:30",
  "19:30",
  "20:30",
];

function buildApp(deps: AppDeps): express.Express {
  const app = express();
  app.use("/versions", ocupacioRouter(deps));
  app.use(notFoundHandler());
  app.use(errorHandler(deps.logger));
  return app;
}

async function consulta(
  app: express.Express,
  query: Record<string, string>,
  id = "1",
): Promise<{ status: number; body: OcupacioBody }> {
  const res = await request(app).get(`/versions/${id}/ocupacio`).query(query);
  return { status: res.status, body: res.body as OcupacioBody };
}

function aula(body: OcupacioBody, codi: string): AulaBody {
  const trobada = body.perAula.find((a) => a.codi === codi);
  if (!trobada) {
    throw new Error(`falta l'aula ${codi}`);
  }
  return trobada;
}

function franja(body: OcupacioBody, dia: string, hora: string): FranjaBody {
  const trobada = body.perFranja.find((f) => f.dia === dia && f.franja === hora);
  if (!trobada) {
    throw new Error(`falta la franja ${dia} ${hora}`);
  }
  return trobada;
}

function errorDe(res: { body: unknown }): string {
  return (res.body as { error: string }).error;
}

describe("GET /versions/:id/ocupacio (BD de fixtures, versio 1 = partida)", () => {
  const deps = testDeps();
  const app = buildApp(deps);

  afterAll(() => {
    deps.db.close();
  });

  it("capcalera: idVersio, setmana, dies i 13 franges de 08:30 a 20:30", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38" });
    expect(status).toBe(200);
    expect(body.idVersio).toBe(1);
    expect(body.setmana).toBe("2026-W38");
    expect(body.dies).toEqual([
      { dia: "L", data: "2026-09-14" },
      { dia: "M", data: "2026-09-15" },
      { dia: "X", data: "2026-09-16" },
      { dia: "J", data: "2026-09-17" },
      { dia: "V", data: "2026-09-18" },
    ]);
    expect(body.franges).toEqual(FRANGES);
  });

  it("perAula: nomes les 7 aules dins de l'aulari, per codi, J/012 no hi surt", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(body.perAula.map((a) => a.codi)).toEqual([
      "Q5/5105",
      "Q7/7101",
      "Q7/7102",
      "Q7/7204",
      "Q8/8103",
      "Q8/8206",
      "Q8/8307",
    ]);
    expect(body.perAula.map((a) => a.codi)).not.toContain("J/012");
  });

  it("perAula: sessions, minutsOcupats i percentatge (270/3750 = 7.2, 90/3750 = 2.4)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(aula(body, "Q8/8103")).toEqual({
      codi: "Q8/8103",
      edifici: "Q8",
      tipus: "Aules docents",
      capacitat: 60,
      ordinaria: true,
      sessions: 3,
      minutsOcupats: 270,
      minutsDisponibles: 3750,
      percentatge: 7.2,
    });
    expect(aula(body, "Q7/7101")).toMatchObject({ sessions: 3, minutsOcupats: 270, percentatge: 7.2, ordinaria: true });
    expect(aula(body, "Q7/7204")).toEqual({
      codi: "Q7/7204",
      edifici: "Q7",
      tipus: "Laboratoris docents",
      capacitat: 24,
      ordinaria: false,
      sessions: 1,
      minutsOcupats: 90,
      minutsDisponibles: 3750,
      percentatge: 2.4,
    });
    for (const codi of ["Q5/5105", "Q7/7102", "Q8/8206", "Q8/8307"]) {
      expect(aula(body, codi)).toMatchObject({ sessions: 0, minutsOcupats: 0, minutsDisponibles: 3750, percentatge: 0 });
    }
    expect(aula(body, "Q7/7102")).toMatchObject({ tipus: "Aules docents", capacitat: 8, ordinaria: true });
    expect(aula(body, "Q8/8206")).toMatchObject({ tipus: "Seminaris", capacitat: 25, ordinaria: false });
    expect(aula(body, "Q8/8307")).toMatchObject({ tipus: "Aules informàtiques", capacitat: 30 });
  });

  it("perFranja: 65 entrades ordenades per dia (L,M,X,J,V) i despres franja", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(body.perFranja).toHaveLength(65);
    const esperat: Array<[string, string, string]> = [];
    const dies: Array<[string, string]> = [
      ["L", "2026-09-14"],
      ["M", "2026-09-15"],
      ["X", "2026-09-16"],
      ["J", "2026-09-17"],
      ["V", "2026-09-18"],
    ];
    for (const [dia, data] of dies) {
      for (const f of FRANGES) {
        esperat.push([dia, data, f]);
      }
    }
    expect(body.perFranja.map((f) => [f.dia, f.data, f.franja])).toEqual(esperat);
  });

  it("L 08:30: S90005 (Q8/8103) -> ocupades 1, lliures 6, ordinariesLliures 2, reservaOk", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "L", "08:30")).toEqual({
      dia: "L",
      data: "2026-09-14",
      franja: "08:30",
      ocupades: 1,
      lliures: 6,
      ordinariesLliures: 2,
      reservaOk: true,
    });
  });

  it("L 09:30 encara ocupada (S90005 fins 10:00); L 10:30 lliure del tot", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "L", "09:30")).toMatchObject({ ocupades: 1, lliures: 6, ordinariesLliures: 2 });
    expect(franja(body, "L", "10:30")).toMatchObject({
      ocupades: 0,
      lliures: 7,
      ordinariesLliures: 3,
      reservaOk: true,
    });
  });

  it("X 09:30: S90009 (Q7/7204 fins 10:00) i S90001 (Q7/7101 des de 10:00) -> ocupades 2, ordinariesLliures 2", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "X", "09:30")).toMatchObject({
      ocupades: 2,
      lliures: 5,
      ordinariesLliures: 2,
      reservaOk: true,
    });
  });

  it("limits exclusius: S90001 acaba a 11:30 -> X 11:30 buida; S90017 (J/012) no ocupa X 12:30", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "X", "10:30")).toMatchObject({ ocupades: 1, ordinariesLliures: 2 });
    expect(franja(body, "X", "11:30")).toMatchObject({ ocupades: 0, lliures: 7, ordinariesLliures: 3 });
    expect(franja(body, "X", "12:30")).toMatchObject({ ocupades: 0, lliures: 7, ordinariesLliures: 3 });
  });

  it("sessio que comenca a mitja franja ocupa la franja anterior: V 08:30 i V 09:30 (S90003 09:00-10:30)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "V", "08:30")).toMatchObject({ ocupades: 1, lliures: 6, ordinariesLliures: 2 });
    expect(franja(body, "V", "09:30")).toMatchObject({ ocupades: 1 });
    expect(franja(body, "V", "10:30")).toMatchObject({ ocupades: 0 });
  });

  it("J 12:00-13:30 (S90019): ocupa J 11:30, 12:30 i no J 13:30", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" });
    expect(franja(body, "J", "11:30")).toMatchObject({ ocupades: 1, ordinariesLliures: 2 });
    expect(franja(body, "J", "12:30")).toMatchObject({ ocupades: 1, ordinariesLliures: 2 });
    expect(franja(body, "J", "13:30")).toMatchObject({ ocupades: 0, ordinariesLliures: 3 });
  });

  it("setmana sense sessions: tot lliure, 3 ordinaries lliures, minutsOcupats 0", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W37" });
    expect(status).toBe(200);
    expect(body.perFranja).toHaveLength(65);
    for (const f of body.perFranja) {
      expect(f.ocupades).toBe(0);
      expect(f.lliures).toBe(7);
      expect(f.ordinariesLliures).toBe(3);
      expect(f.reservaOk).toBe(true);
    }
    for (const a of body.perAula) {
      expect(a.sessions).toBe(0);
      expect(a.minutsOcupats).toBe(0);
    }
  });

  it("filtre tipus Seminaris: perAula nomes Q8/8206, ordinariesLliures sense filtrar", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", tipus: "Seminaris" });
    expect(status).toBe(200);
    expect(body.perAula.map((a) => a.codi)).toEqual(["Q8/8206"]);
    expect(aula(body, "Q8/8206")).toMatchObject({ sessions: 0, minutsOcupats: 0, percentatge: 0 });
    // L 08:30: del conjunt (1 aula) 0 ocupades i 1 lliure; ordinaries igual que sense filtre (2)
    expect(franja(body, "L", "08:30")).toMatchObject({ ocupades: 0, lliures: 1, ordinariesLliures: 2, reservaOk: true });
    expect(franja(body, "X", "09:30")).toMatchObject({ ocupades: 0, lliures: 1, ordinariesLliures: 2 });
  });

  it("filtre tipus Aules docents: 3 aules, ocupades/lliures sobre aquest conjunt", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", tipus: "Aules docents" });
    expect(body.perAula.map((a) => a.codi)).toEqual(["Q7/7101", "Q7/7102", "Q8/8103"]);
    expect(franja(body, "L", "08:30")).toMatchObject({ ocupades: 1, lliures: 2, ordinariesLliures: 2 });
    // X 09:30: Q7/7204 (laboratori) no compta; nomes S90001 a Q7/7101
    expect(franja(body, "X", "09:30")).toMatchObject({ ocupades: 1, lliures: 2, ordinariesLliures: 2 });
  });

  it("filtre tipus amb accent: Aules informàtiques -> nomes Q8/8307", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", tipus: "Aules informàtiques" });
    expect(status).toBe(200);
    expect(body.perAula.map((a) => a.codi)).toEqual(["Q8/8307"]);
  });

  it("versio inexistent -> 404 not_found", async () => {
    const res = await request(app).get("/versions/999/ocupacio").query({ setmana: "2026-W38" });
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: "not_found" });
  });

  it.each(["abc", "0", "-3"])("id %s -> 400", async (id) => {
    const res = await request(app).get(`/versions/${id}/ocupacio`).query({ setmana: "2026-W38" });
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  it("sense setmana -> 400", async () => {
    const res = await request(app).get("/versions/1/ocupacio");
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  // Punt de contracte: 2027-W53 passa el regex pero no existeix (2027 te 52 setmanes); es demana 400, no 500.
  it.each(["2026-38", "2027-W53", "2026-W00", "2026-W54", "2026-W38'; DROP TABLE aula;--", ""])(
    "setmana %j -> 400",
    async (setmana) => {
      const res = await request(app).get("/versions/1/ocupacio").query({ setmana });
      expect(res.status).toBe(400);
      expect(errorDe(res)).toBe("invalid_request");
    },
  );

  it.each(["Seminari", "seminaris", "", "Seminaris' OR '1'='1", "../x"])("tipus %j -> 400", async (tipus) => {
    const res = await request(app).get("/versions/1/ocupacio").query({ setmana: "2026-W38", tipus });
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  it("parametres repetits (tipus doble, setmana doble) -> 400, no 500", async () => {
    const a = await request(app).get("/versions/1/ocupacio?setmana=2026-W38&tipus=Seminaris&tipus=Aules%20docents");
    expect(a.status).toBe(400);
    const b = await request(app).get("/versions/1/ocupacio?setmana=2026-W38&setmana=2026-W39");
    expect(b.status).toBe(400);
  });
});

describe("GET /versions/:id/ocupacio (versio 2: reserva insuficient, solapament i retall, BD escrivible)", () => {
  const copia = openWritableCopy();
  const base = testDeps();
  const app = buildApp({ ...base, db: copia.db });

  beforeAll(() => {
    copia.db.exec(`
      INSERT INTO versio_horari (id_versio, nom) VALUES (2, 'solapada');
      INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data)
        SELECT 2, id_sessio, dia, h_ini, aula, data FROM assignacio WHERE id_versio = 1;
      UPDATE assignacio SET dia = 'L', h_ini = '08:30' WHERE id_versio = 2 AND id_sessio = 'S90015';
      UPDATE assignacio SET dia = 'X', h_ini = '10:30' WHERE id_versio = 2 AND id_sessio = 'S90003';
      UPDATE assignacio SET dia = 'V', h_ini = '20:30' WHERE id_versio = 2 AND id_sessio = 'S90019';
    `);
    // S90015 (Q7/7101, 90 min) passa a L 08:30 -> amb S90005 (Q8/8103) hi ha 2 ordinaries ocupades.
    // S90003 (Q7/7101, 90 min) passa a X 10:30, solapada amb S90001 (X 10:00-11:30): unio 10:00-12:00 = 120 min.
    // S90019 (Q8/8103, 90 min) passa a V 20:30: acaba a 22:00, retallada a 21:00 = 30 min.
  });

  afterAll(() => {
    copia.dispose();
    base.db.close();
  });

  it("dues ordinaries ocupades a la mateixa franja: ordinariesLliures 1 i reservaOk false", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38" }, "2");
    expect(status).toBe(200);
    expect(franja(body, "L", "08:30")).toEqual({
      dia: "L",
      data: "2026-09-14",
      franja: "08:30",
      ocupades: 2,
      lliures: 5,
      ordinariesLliures: 1,
      reservaOk: false,
    });
    expect(franja(body, "L", "09:30")).toMatchObject({ ocupades: 2, ordinariesLliures: 1, reservaOk: false });
    expect(franja(body, "L", "10:30")).toMatchObject({ ocupades: 0, ordinariesLliures: 3, reservaOk: true });
  });

  it("solapament a la mateixa aula: la unio es compta una vegada (Q7/7101 = 90 + 120 = 210 min, 3 sessions)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" }, "2");
    // S90015 (L) 90 + {S90001 10:00-11:30 U S90003 10:30-12:00 = 10:00-12:00} 120
    expect(aula(body, "Q7/7101")).toMatchObject({ sessions: 3, minutsOcupats: 210, percentatge: 5.6 });
  });

  it("franja amb dues sessions a la mateixa aula compta l'aula una sola vegada; el final usa durada_min", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" }, "2");
    expect(franja(body, "X", "10:30")).toMatchObject({ ocupades: 1, lliures: 6, ordinariesLliures: 2 });
    // S90003 acaba a 12:00, per tant ocupa X 11:30 (11:30-12:30)
    expect(franja(body, "X", "11:30")).toMatchObject({ ocupades: 1, ordinariesLliures: 2 });
    expect(franja(body, "X", "12:30")).toMatchObject({ ocupades: 0 });
  });

  it("sessio que sobrepassa les 21:00: retallada a la finestra (Q8/8103 = 90 + 90 + 30 = 210 min)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" }, "2");
    expect(aula(body, "Q8/8103")).toMatchObject({ sessions: 3, minutsOcupats: 210, percentatge: 5.6 });
    expect(franja(body, "V", "20:30")).toMatchObject({ ocupades: 1, lliures: 6, ordinariesLliures: 2 });
    expect(franja(body, "V", "19:30")).toMatchObject({ ocupades: 0 });
  });

  it("la versio 1 no es veu afectada", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38" }, "1");
    expect(franja(body, "L", "08:30")).toMatchObject({ ocupades: 1, ordinariesLliures: 2, reservaOk: true });
    expect(aula(body, "Q7/7101")).toMatchObject({ minutsOcupats: 270 });
  });

  it("amb filtre tipus Seminaris la reserva continua calculant-se sobre totes les ordinaries", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", tipus: "Seminaris" }, "2");
    expect(franja(body, "L", "08:30")).toMatchObject({ ocupades: 0, lliures: 1, ordinariesLliures: 1, reservaOk: false });
  });
});

describe("GET /versions/:id/ocupacio (sessio recuperada, BD escrivible)", () => {
  const copia = openWritableCopy();
  const base = testDeps();
  const app = buildApp({ ...base, db: copia.db });

  beforeAll(() => {
    copia.db.exec(`
      INSERT INTO versio_horari (id_versio, nom) VALUES (2, 'recuperada');
      INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data)
        SELECT 2, id_sessio, dia, h_ini, aula, data FROM assignacio WHERE id_versio = 1;
      UPDATE assignacio SET dia = 'L', h_ini = '09:00', data = '2026-09-28' WHERE id_versio = 2 AND id_sessio = 'S90003';
    `);
    // S90003 (Q7/7101, 90 min, V 09:00 de W38) es recupera el dilluns 2026-09-28 (W40) a les 09:00.
  });

  afterAll(() => {
    copia.dispose();
    base.db.close();
  });

  it("compta a la setmana de la recuperacio (perAula i perFranja) i no a l'original", async () => {
    const w40 = await consulta(app, { setmana: "2026-W40" }, "2");
    expect(aula(w40.body, "Q7/7101")).toMatchObject({ sessions: 1, minutsOcupats: 90 });
    expect(franja(w40.body, "L", "08:30")).toMatchObject({ data: "2026-09-28", ocupades: 1 });
    expect(franja(w40.body, "L", "09:30")).toMatchObject({ ocupades: 1 });
    expect(franja(w40.body, "L", "10:30")).toMatchObject({ ocupades: 0 });

    const w38 = await consulta(app, { setmana: "2026-W38" }, "2");
    const original = await consulta(app, { setmana: "2026-W38" }, "1");
    expect(aula(w38.body, "Q7/7101").sessions).toBe(aula(original.body, "Q7/7101").sessions - 1);
    expect(aula(w38.body, "Q7/7101").minutsOcupats).toBe(aula(original.body, "Q7/7101").minutsOcupats - 90);
    expect(franja(w38.body, "V", "09:30")).toMatchObject({ ocupades: 0 });
  });

  it("la versio 1 no te res a W40", async () => {
    const { body } = await consulta(app, { setmana: "2026-W40" }, "1");
    expect(aula(body, "Q7/7101")).toMatchObject({ sessions: 0, minutsOcupats: 0 });
  });
});
