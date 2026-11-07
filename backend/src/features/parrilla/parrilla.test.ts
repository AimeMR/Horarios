import express from "express";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openWritableCopy, testDeps } from "../../../test/helpers.js";
import type { AppDeps } from "../../http/app.js";
import { errorHandler, notFoundHandler } from "../../http/errors.js";
import { parrillaRouter } from "./parrilla.controller.js";

// Cada valor esperado se deriva de tests/fixtures/paquet_fals (sessions.csv, proposta_partida.csv, calendari.csv).
// Setmana 2026-W38 = dilluns 2026-09-14 .. divendres 2026-09-18.

interface ItemBody {
  idSessio: string;
  data: string;
  dia: string;
  hIni: string;
  hFi: string;
  duradaMin: number;
  aula: string | null;
  assignatura: { codi: string; nom: string };
  grup: { idGrup: string; grup: string; tipus: string };
  alumnes: number;
  profes: string[];
  cohorts: string[];
  idCompartida: string | null;
  fixadaMotiu: string | null;
  moguda: boolean;
  canviAula: boolean;
  recuperada: boolean;
}

interface ParrillaBody {
  idVersio: number;
  setmana: string;
  dies: Array<{ dia: string; data: string }>;
  filtre: Record<string, string>;
  calendari: Array<{ data: string; tipus: string; hIni: string | null; hFi: string | null; motiu: string }>;
  items: ItemBody[];
  truncat: boolean;
}

function buildApp(deps: AppDeps): express.Express {
  const app = express();
  app.use("/versions", parrillaRouter(deps));
  app.use(notFoundHandler());
  app.use(errorHandler(deps.logger));
  return app;
}

async function consulta(
  app: express.Express,
  query: Record<string, string>,
  id = "1",
): Promise<{ status: number; body: ParrillaBody }> {
  const res = await request(app).get(`/versions/${id}/parrilla`).query(query);
  return { status: res.status, body: res.body as ParrillaBody };
}

function ids(body: ParrillaBody): string[] {
  return body.items.map((i) => i.idSessio);
}

function item(body: ParrillaBody, idSessio: string): ItemBody {
  const trobat = body.items.find((i) => i.idSessio === idSessio);
  if (!trobat) {
    throw new Error(`falta ${idSessio} a la resposta`);
  }
  return trobat;
}

function errorDe(res: { body: unknown }): string {
  return (res.body as { error: string }).error;
}

describe("GET /versions/:id/parrilla (BD de fixtures, versio 1 = partida)", () => {
  const deps = testDeps();
  const app = buildApp(deps);

  afterAll(() => {
    deps.db.close();
  });

  it("cohort GFA:1r a 2026-W38: items exactes, ordre data/hIni/aula/idSessio", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" });
    expect(status).toBe(200);
    expect(body.idVersio).toBe(1);
    expect(body.setmana).toBe("2026-W38");
    // 900001 i 900002 son de GFA:1r; a la W38: S90005 (L), S90013 (M), S90009 08:30 i S90001 10:00 (X), S90015 (J), S90003 (V)
    expect(ids(body)).toEqual(["S90005", "S90013", "S90009", "S90001", "S90015", "S90003"]);
    expect(body.truncat).toBe(false);
    expect(body.filtre).toEqual({ cohort: "GFA:1r" });
    expect(body.dies).toEqual([
      { dia: "L", data: "2026-09-14" },
      { dia: "M", data: "2026-09-15" },
      { dia: "X", data: "2026-09-16" },
      { dia: "J", data: "2026-09-17" },
      { dia: "V", data: "2026-09-18" },
    ]);
    // calendari.csv no te cap data entre 2026-09-14 i 2026-09-18
    expect(body.calendari).toEqual([]);
  });

  it("item complet: S90005 (TE/81, un docent, cap marca)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" });
    expect(item(body, "S90005")).toEqual({
      idSessio: "S90005",
      data: "2026-09-14",
      dia: "L",
      hIni: "08:30",
      hFi: "10:00",
      duradaMin: 90,
      aula: "Q8/8103",
      assignatura: { codi: "900001", nom: "Assignatura Falsa 1" },
      grup: { idGrup: "900001·TE/81", grup: "TE/81", tipus: "TE" },
      alumnes: 50,
      profes: ["D901"],
      cohorts: ["GFA:1r"],
      idCompartida: null,
      fixadaMotiu: null,
      moguda: false,
      canviAula: false,
      recuperada: false,
    });
  });

  it("profes ordenats i sense docents: S90013 -> [D903, D904]; S90003 -> []", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" });
    expect(item(body, "S90013").profes).toEqual(["D903", "D904"]);
    expect(item(body, "S90013").grup.idGrup).toBe("900002·TE/31");
    expect(item(body, "S90013").alumnes).toBe(45);
    expect(item(body, "S90003").profes).toEqual([]);
    expect(item(body, "S90003").grup.idGrup).toBe("900001·PAUL/812");
  });

  it("cap item d'una versio sense moviments esta marcat com a moguda/canviAula/recuperada", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" });
    for (const it2 of body.items) {
      expect(it2.moguda).toBe(false);
      expect(it2.canviAula).toBe(false);
      expect(it2.recuperada).toBe(false);
    }
  });

  it("filtre aula Q7/7101: S90001 (X), S90015 (J), S90003 (V)", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", aula: "Q7/7101" });
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["S90001", "S90015", "S90003"]);
    expect(body.filtre).toEqual({ aula: "Q7/7101" });
  });

  it("filtre profe D906: S90017 (aula externa J/012, fixada) i S90019", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", profe: "D906" });
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["S90017", "S90019"]);
    expect(body.filtre).toEqual({ profe: "D906" });
    const externa = item(body, "S90017");
    expect(externa.aula).toBe("J/012");
    expect(externa.data).toBe("2026-09-16");
    expect(externa.hIni).toBe("12:00");
    expect(externa.hFi).toBe("13:30");
    expect(externa.grup.idGrup).toBe("900003·PAUL/415");
    expect(externa.cohorts).toEqual(["GFB:2n", "GFC:2n"]);
    expect(externa.fixadaMotiu).toBe("R1: GFB 2n i GFC 2n");
  });

  it("filtre assignatura 900001: S90005, S90001, S90003", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", assignatura: "900001" });
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["S90005", "S90001", "S90003"]);
    expect(body.filtre).toEqual({ assignatura: "900001" });
  });

  it("filtre grup 900002·TE/31: nomes S90013 (no barreja TE/310)", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", grup: "900002·TE/31" });
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["S90013"]);
    expect(body.filtre).toEqual({ grup: "900002·TE/31" });
  });

  it("filtres combinats amb AND: aula Q8/8103 + cohort GFA:1r exclou S90019 (GFB:2n)", async () => {
    const sols = await consulta(app, { setmana: "2026-W38", aula: "Q8/8103" });
    expect(ids(sols.body)).toEqual(["S90005", "S90013", "S90019"]);
    const combinat = await consulta(app, { setmana: "2026-W38", aula: "Q8/8103", cohort: "GFA:1r" });
    expect(combinat.status).toBe(200);
    expect(ids(combinat.body)).toEqual(["S90005", "S90013"]);
    expect(combinat.body.filtre).toEqual({ aula: "Q8/8103", cohort: "GFA:1r" });
  });

  it("filtres combinats: cohort GFA:1r + profe D903 -> S90013 (M) i S90009 (X)", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r", profe: "D903" });
    expect(ids(body)).toEqual(["S90013", "S90009"]);
  });

  it("filtres combinats sense interseccio -> items buit", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", profe: "D906", cohort: "GFA:1r" });
    expect(status).toBe(200);
    expect(body.items).toEqual([]);
    expect(body.truncat).toBe(false);
  });

  it("setmana sense sessions -> items [] amb els 5 dies", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W37", cohort: "GFA:1r" });
    expect(status).toBe(200);
    expect(body.items).toEqual([]);
    expect(body.dies).toHaveLength(5);
    expect(body.dies[0]).toEqual({ dia: "L", data: "2026-09-07" });
  });

  it("sessio sense aula: aula null (S90021, cohort GFA:?, W39)", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W39", cohort: "GFA:?" });
    expect(status).toBe(200);
    expect(ids(body)).toEqual(["S90021"]);
    expect(item(body, "S90021").aula).toBeNull();
    expect(item(body, "S90021").hIni).toBe("16:00");
    expect(item(body, "S90021").hFi).toBe("17:30");
  });

  it("calendari: festiu sense hores a 2026-W42 (2026-10-12) i parella compartida CP9001", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W42", cohort: "MFA:M" });
    expect(status).toBe(200);
    expect(body.calendari).toEqual([
      { data: "2026-10-12", tipus: "festiu", hIni: null, hFi: null, motiu: "Festa fictícia" },
    ]);
    // S90024 i S90028: mateix dia, hora i aula -> desempat per idSessio
    expect(ids(body)).toEqual(["S90024", "S90028"]);
    expect(item(body, "S90024").idCompartida).toBe("CP9001");
    expect(item(body, "S90024").profes).toEqual(["D908"]);
    expect(item(body, "S90028").profes).toEqual(["D909"]);
  });

  it("calendari: aturada amb hores a 2027-W03 (2027-01-20 08:00-14:00)", async () => {
    const { status, body } = await consulta(app, { setmana: "2027-W03", cohort: "GFA:1r" });
    expect(status).toBe(200);
    expect(body.calendari).toEqual([
      { data: "2027-01-20", tipus: "aturada", hIni: "08:00", hFi: "14:00", motiu: "Aturada fictícia" },
    ]);
    expect(ids(body)).toEqual(["S90008"]);
    expect(item(body, "S90008").data).toBe("2027-01-18");
  });

  it("versio inexistent -> 404 not_found", async () => {
    const res = await request(app).get("/versions/999/parrilla").query({ setmana: "2026-W38", aula: "Q7/7101" });
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: "not_found" });
  });

  it.each(["abc", "0", "-1", "1.5"])("id %s -> 400 invalid_request", async (id) => {
    const res = await request(app).get(`/versions/${id}/parrilla`).query({ setmana: "2026-W38", aula: "Q7/7101" });
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  it("sense cap filtre -> 400", async () => {
    const res = await request(app).get("/versions/1/parrilla").query({ setmana: "2026-W38" });
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  it("sense setmana -> 400", async () => {
    const res = await request(app).get("/versions/1/parrilla").query({ cohort: "GFA:1r" });
    expect(res.status).toBe(400);
  });

  // Punt de contracte: el regex de setmanaSchema accepta 2027-W53, pero 2027 nomes te 52 setmanes ISO.
  // Es demana 400 (no 500 per RangeError de dillunsDeSetmana).
  it.each(["2026-38", "2027-W53", "2026-W00", "2026-W54", "26-W38", "2026-W3", ""])(
    "setmana %j -> 400",
    async (setmana) => {
      const res = await request(app).get("/versions/1/parrilla").query({ setmana, cohort: "GFA:1r" });
      expect(res.status).toBe(400);
      expect(errorDe(res)).toBe("invalid_request");
    },
  );

  it.each([
    ["aula", "Q7-7101"],
    ["aula", "Q7/7101/1"],
    ["aula", "Q7/"],
    ["cohort", "GFA:5e"],
    ["cohort", "GFA"],
    ["cohort", "GFA:1r:x"],
    ["profe", "D90 1"],
    ["profe", "D901-"],
    ["assignatura", "90000a"],
    ["assignatura", "1234567890123"],
    ["grup", "900001-TE/81"],
    ["grup", "900001·XX/81"],
    ["grup", "900001·TE/1234567"],
  ])("filtre %s amb format invalid %j -> 400", async (clau, valor) => {
    const res = await request(app)
      .get("/versions/1/parrilla")
      .query({ setmana: "2026-W38", [clau]: valor });
    expect(res.status).toBe(400);
    expect(errorDe(res)).toBe("invalid_request");
  });

  it.each([
    ["aula", "Q7/7101' OR '1'='1"],
    ["cohort", "GFA:1r'; DROP TABLE aula;--"],
    ["profe", "D901' OR 1=1--"],
    ["assignatura", "1 OR 1=1"],
    ["grup", "900001·TE/81' UNION SELECT 1--"],
    ["aula", "../../etc/passwd"],
  ])("valor d'injeccio a %s -> 400, mai 500, i no es retorna el valor", async (clau, valor) => {
    const res = await request(app)
      .get("/versions/1/parrilla")
      .query({ setmana: "2026-W38", [clau]: valor });
    expect(res.status).toBe(400);
    expect(JSON.stringify(res.body)).not.toContain(valor);
  });

  it("injeccio a setmana -> 400", async () => {
    const res = await request(app)
      .get("/versions/1/parrilla")
      .query({ setmana: "2026-W38'; DROP TABLE sessio;--", cohort: "GFA:1r" });
    expect(res.status).toBe(400);
  });

  it("parametre repetit (aula=a&aula=b) -> 400, no 500", async () => {
    const res = await request(app).get("/versions/1/parrilla?setmana=2026-W38&aula=Q7/7101&aula=Q8/8103");
    expect(res.status).toBe(400);
  });

  it("l'injeccio no ha alterat la BD: continua responent igual", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", aula: "Q7/7101" });
    expect(ids(body)).toEqual(["S90001", "S90015", "S90003"]);
  });
});

describe("GET /versions/:id/parrilla (versio 2 amb sessions mogudes, BD escrivible)", () => {
  const copia = openWritableCopy();
  const base = testDeps();
  const app = buildApp({ ...base, db: copia.db });

  beforeAll(() => {
    copia.db.exec(`
      INSERT INTO versio_horari (id_versio, nom) VALUES (2, 'moguda');
      INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data)
        SELECT 2, id_sessio, dia, h_ini, aula, data FROM assignacio WHERE id_versio = 1;
      UPDATE assignacio SET dia = 'J' WHERE id_versio = 2 AND id_sessio = 'S90005';
      UPDATE assignacio SET aula = 'Q7/7102' WHERE id_versio = 2 AND id_sessio = 'S90013';
      UPDATE assignacio SET dia = 'L', data = '2026-09-28' WHERE id_versio = 2 AND id_sessio = 'S90003';
    `);
    // S90005 (L 08:30 Q8/8103) passa a dijous; S90013 (M) canvia d'aula; S90003 (V 09:00) recuperada el 2026-09-28 (W40)
  });

  afterAll(() => {
    copia.db.close();
    base.db.close();
  });

  it("la versio 1 no es veu afectada pels canvis de la versio 2", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" }, "1");
    expect(ids(body)).toEqual(["S90005", "S90013", "S90009", "S90001", "S90015", "S90003"]);
  });

  it("W38 versio 2: S90005 mogut a J (data recalculada), S90013 canvia d'aula, S90003 ja no hi es", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" }, "2");
    expect(status).toBe(200);
    expect(body.idVersio).toBe(2);
    // M S90013 | X S90009 08:30, S90001 10:00 | J 08:30: Q7/7101 (S90015) abans de Q8/8103 (S90005)
    expect(ids(body)).toEqual(["S90013", "S90009", "S90001", "S90015", "S90005"]);

    const moguda = item(body, "S90005");
    expect(moguda.dia).toBe("J");
    expect(moguda.data).toBe("2026-09-17");
    expect(moguda.hIni).toBe("08:30");
    expect(moguda.hFi).toBe("10:00");
    expect(moguda.moguda).toBe(true);
    expect(moguda.canviAula).toBe(false);
    expect(moguda.recuperada).toBe(false);

    const aula = item(body, "S90013");
    expect(aula.aula).toBe("Q7/7102");
    expect(aula.data).toBe("2026-09-15");
    expect(aula.canviAula).toBe(true);
    expect(aula.moguda).toBe(false);
    expect(aula.recuperada).toBe(false);

    const quieta = item(body, "S90001");
    expect(quieta.moguda).toBe(false);
    expect(quieta.canviAula).toBe(false);
  });

  it("sessio recuperada: apareix a la setmana de assignacio.data (W40) i no a l'original (W38)", async () => {
    const w40 = await consulta(app, { setmana: "2026-W40", cohort: "GFA:1r" }, "2");
    expect(w40.status).toBe(200);
    expect(ids(w40.body)).toEqual(["S90003"]);
    const recuperada = item(w40.body, "S90003");
    expect(recuperada.data).toBe("2026-09-28");
    expect(recuperada.dia).toBe("L");
    expect(recuperada.hIni).toBe("09:00");
    expect(recuperada.hFi).toBe("10:30");
    expect(recuperada.recuperada).toBe(true);
    expect(recuperada.moguda).toBe(true);
    expect(recuperada.canviAula).toBe(false);

    const w38 = await consulta(app, { setmana: "2026-W38", cohort: "GFA:1r" }, "2");
    expect(ids(w38.body)).not.toContain("S90003");
  });

  it("la versio 1 no mostra S90003 a W40", async () => {
    const { body } = await consulta(app, { setmana: "2026-W40", cohort: "GFA:1r" }, "1");
    expect(body.items).toEqual([]);
  });

  it("filtre aula respecta l'aula de la versio: Q7/7102 a W38 versio 2 = S90013", async () => {
    const { body } = await consulta(app, { setmana: "2026-W38", aula: "Q7/7102" }, "2");
    expect(ids(body)).toEqual(["S90013"]);
    const v1 = await consulta(app, { setmana: "2026-W38", aula: "Q7/7102" }, "1");
    expect(v1.body.items).toEqual([]);
  });
});

describe("GET /versions/:id/parrilla (docencia vigent, BD escrivible)", () => {
  const copia = openWritableCopy();
  const base = testDeps();
  const app = buildApp({ ...base, db: copia.db });

  beforeAll(() => {
    // La docencia de D906 acaba el 2026-09-15; S90017 (09-16) i S90019 (09-17) tenen data_partida posterior
    copia.db.exec("UPDATE docencia SET vigent_fins = '2026-09-15' WHERE id_profe = 'D906'");
  });

  afterAll(() => {
    copia.db.close();
    base.db.close();
  });

  it("profe sense docencia vigent a la data de la sessio -> items []", async () => {
    const { status, body } = await consulta(app, { setmana: "2026-W38", profe: "D906" });
    expect(status).toBe(200);
    expect(body.items).toEqual([]);
  });
});
