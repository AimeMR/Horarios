import express from "express";
import request from "supertest";
import { afterAll, describe, expect, it } from "vitest";
import { testDeps } from "../../../test/helpers.js";
import { errorHandler, notFoundHandler } from "../../http/errors.js";
import { aulesRouter } from "./aules.controller.js";

interface AulaBody {
  codi: string;
  edifici: string | null;
  espina: string;
  planta: number;
  tipus: string | null;
  capacitat: number | null;
  ordinaria: boolean;
  integrat: boolean;
  nomesPlab: boolean;
  dinsAulari: boolean;
  admetNoves: boolean;
  descripcio: string | null;
}
interface PageBody {
  items: AulaBody[];
  total: number;
  limit: number;
  offset: number;
}
interface ErrorBody {
  error: string;
  issues?: { path: string; message: string }[];
}

const SENTINELLA = "ZZ_VALOR_9";

const deps = testDeps();
const app = express().use("/aules", aulesRouter(deps)).use(notFoundHandler()).use(errorHandler(deps.logger));

afterAll(() => {
  deps.db.close();
});

async function llistar(query: Record<string, string | number>): Promise<{ status: number; body: PageBody }> {
  const res = await request(app).get("/aules").query(query);
  return { status: res.status, body: res.body as PageBody };
}

const codis = (page: PageBody): string[] => page.items.map((a) => a.codi);

// aules.csv (7) + 5 externes (J/012, J/102, J/124, B3/0021, QC/1082) = 12; orden binario de SQLite por codi.
const TOTS_ORDENATS = [
  "B3/0021",
  "J/012",
  "J/102",
  "J/124",
  "Q5/5105",
  "Q7/7101",
  "Q7/7102",
  "Q7/7204",
  "Q8/8103",
  "Q8/8206",
  "Q8/8307",
  "QC/1082",
];

describe("GET /aules", () => {
  it("devuelve la primera pagina por defecto ordenada por codi ASC", async () => {
    const { status, body } = await llistar({});
    expect(status).toBe(200);
    expect(body.total).toBe(12);
    expect(body.limit).toBe(100);
    expect(body.offset).toBe(0);
    expect(codis(body)).toEqual(TOTS_ORDENATS);
  });

  it("expone AulaDto con exactamente las claves del contrato y booleanos reales", async () => {
    const { body } = await llistar({});
    const aula = body.items.find((a) => a.codi === "Q7/7101");
    expect(aula).toEqual({
      codi: "Q7/7101",
      edifici: "Q7",
      espina: "Q7",
      planta: 7,
      tipus: "Aules docents",
      capacitat: 40,
      ordinaria: true,
      integrat: false,
      nomesPlab: false,
      dinsAulari: true,
      admetNoves: true,
      descripcio: "Aula ordinaria fictícia de 40 places",
    });
    const claus = [
      "admetNoves",
      "capacitat",
      "codi",
      "descripcio",
      "dinsAulari",
      "edifici",
      "espina",
      "integrat",
      "nomesPlab",
      "ordinaria",
      "planta",
      "tipus",
    ];
    for (const item of body.items) {
      expect(Object.keys(item).sort()).toEqual(claus);
      const marques = [item.ordinaria, item.integrat, item.nomesPlab, item.dinsAulari, item.admetNoves];
      expect(marques.map((m) => typeof m)).toEqual(Array<string>(5).fill("boolean"));
    }
  });

  it("deriva espina y planta del codi (planta = primer digito tras la barra)", async () => {
    const { body } = await llistar({});
    const resum = body.items.map((a) => [a.codi, a.espina, a.planta]);
    expect(resum).toEqual([
      ["B3/0021", "B3", 0],
      ["J/012", "J", 0],
      ["J/102", "J", 1],
      ["J/124", "J", 1],
      ["Q5/5105", "Q5", 5],
      // Criterio del verificador (check.py `passadis`): planta = primer dígito tras la barra.
      ["Q7/7101", "Q7", 7],
      ["Q7/7102", "Q7", 7],
      ["Q7/7204", "Q7", 7],
      ["Q8/8103", "Q8", 8],
      ["Q8/8206", "Q8", 8],
      ["Q8/8307", "Q8", 8],
      ["QC/1082", "QC", 1],
    ]);
  });

  it("marca integrat y nomesPlab segun la carga y las externas como fuera del aulario", async () => {
    const { body } = await llistar({});
    const per = (codi: string): AulaBody | undefined => body.items.find((a) => a.codi === codi);
    // la descripcion de Q7/7204 contiene "integrat"; Q5 es espina nomes_plab
    expect(per("Q7/7204")?.integrat).toBe(true);
    expect(per("Q5/5105")?.nomesPlab).toBe(true);
    expect(per("Q5/5105")?.integrat).toBe(false);
    expect(per("J/012")).toMatchObject({
      edifici: null,
      tipus: null,
      capacitat: null,
      ordinaria: false,
      dinsAulari: false,
      admetNoves: false,
      descripcio: null,
    });
  });

  describe("filtro tipus", () => {
    it.each([
      ["Aules docents", ["Q7/7101", "Q7/7102", "Q8/8103"]],
      ["Laboratoris docents", ["Q5/5105", "Q7/7204"]],
      ["Seminaris", ["Q8/8206"]],
      ["Aules informàtiques", ["Q8/8307"]],
    ])("tipus=%s devuelve solo ese tipo y excluye las externas", async (tipus, esperats) => {
      const { status, body } = await llistar({ tipus });
      expect(status).toBe(200);
      expect(codis(body)).toEqual(esperats);
      expect(body.total).toBe(esperats.length);
      expect(body.items.every((a) => a.tipus === tipus)).toBe(true);
    });
  });

  describe("filtro capacitat_min", () => {
    it("es inclusivo en el limite y excluye capacidad NULL", async () => {
      // capacidades: 7101=40, 7102=8, 8103=60, 7204=24, 5105=20, 8206=25, 8307=30; externas NULL
      const { body } = await llistar({ capacitat_min: 30 });
      expect(codis(body)).toEqual(["Q7/7101", "Q8/8103", "Q8/8307"]);
      expect(body.total).toBe(3);
    });

    it("31 excluye la de capacidad 30", async () => {
      const { body } = await llistar({ capacitat_min: 31 });
      expect(codis(body)).toEqual(["Q7/7101", "Q8/8103"]);
    });

    it("0 devuelve las 7 con capacidad y ninguna externa", async () => {
      const { body } = await llistar({ capacitat_min: 0 });
      expect(body.total).toBe(7);
      expect(codis(body)).not.toContain("J/012");
    });

    it("1000 (maximo) es valido y no devuelve nada", async () => {
      const { status, body } = await llistar({ capacitat_min: 1000 });
      expect(status).toBe(200);
      expect(body.total).toBe(0);
      expect(body.items).toEqual([]);
    });
  });

  it("combina tipus y capacitat_min con AND", async () => {
    const { body } = await llistar({ tipus: "Aules docents", capacitat_min: 40 });
    expect(codis(body)).toEqual(["Q7/7101", "Q8/8103"]);
    expect(body.total).toBe(2);
  });

  describe("paginacion", () => {
    it("limit y offset recortan items pero total no cambia", async () => {
      const { status, body } = await llistar({ limit: 3, offset: 2 });
      expect(status).toBe(200);
      expect(codis(body)).toEqual(TOTS_ORDENATS.slice(2, 5));
      expect(body.total).toBe(12);
      expect(body.limit).toBe(3);
      expect(body.offset).toBe(2);
    });

    it("offset mas alla del total devuelve items vacios con el total real", async () => {
      const { body } = await llistar({ offset: 50 });
      expect(body.items).toEqual([]);
      expect(body.total).toBe(12);
    });

    it("la paginacion se aplica sobre el resultado filtrado", async () => {
      const { body } = await llistar({ tipus: "Aules docents", limit: 1, offset: 1 });
      expect(codis(body)).toEqual(["Q7/7102"]);
      expect(body.total).toBe(3);
    });

    it("acepta limit=500", async () => {
      const { status, body } = await llistar({ limit: 500 });
      expect(status).toBe(200);
      expect(body.limit).toBe(500);
    });
  });

  describe("entrada invalida", () => {
    it.each([
      ["tipus", SENTINELLA],
      ["tipus", "aules docents"],
      ["capacitat_min", -1],
      ["capacitat_min", 1001],
      ["capacitat_min", "abc"],
      ["capacitat_min", "1.5"],
      ["capacitat_min", SENTINELLA],
      ["limit", 0],
      ["limit", 501],
      ["limit", "abc"],
      ["offset", -1],
      ["offset", SENTINELLA],
    ])("%s=%s responde 400 invalid_request sin eco del valor", async (clau, valor) => {
      const res = await request(app)
        .get("/aules")
        .query({ [clau]: valor });
      const body = res.body as ErrorBody;
      expect(res.status).toBe(400);
      expect(body.error).toBe("invalid_request");
      expect(Array.isArray(body.issues)).toBe(true);
      expect(body.issues?.length).toBeGreaterThan(0);
      expect(JSON.stringify(body)).not.toContain(SENTINELLA);
    });

    it.each(["x' OR 1=1 --", "'; DROP TABLE aula; --", "Seminaris' OR '1'='1"])(
      "tipus=%s se rechaza con 400 y nunca 500",
      async (tipus) => {
        const res = await request(app).get("/aules").query({ tipus });
        expect(res.status).toBe(400);
        expect((res.body as ErrorBody).error).toBe("invalid_request");
      },
    );

    it("capacitat_min con SQL se rechaza con 400", async () => {
      const res = await request(app).get("/aules").query({ capacitat_min: "0 OR 1=1" });
      expect(res.status).toBe(400);
    });

    it("tras los intentos de inyeccion la tabla sigue intacta", async () => {
      await request(app).get("/aules").query({ tipus: "'; DROP TABLE aula; --" });
      const { body } = await llistar({});
      expect(body.total).toBe(12);
    });
  });
});
