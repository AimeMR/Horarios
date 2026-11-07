import express from "express";
import request from "supertest";
import { afterAll, describe, expect, it } from "vitest";
import { testDeps } from "../../../test/helpers.js";
import { errorHandler, notFoundHandler } from "../../http/errors.js";
import { versionsRouter } from "./versions.controller.js";

interface VersioBody {
  id: number;
  nom: string;
  idVersioReferencia: number | null;
  idEscenari: string | null;
  semestre: 1 | 2 | null;
  mode: string;
  creadaEl: string;
  veredicte: string | null;
}
interface AssignacioBody {
  idSessio: string;
  dia: string;
  hIni: string;
  aula: string | null;
  data: string | null;
}
interface PageBody<T> {
  items: T[];
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
const app = express().use("/versions", versionsRouter(deps)).use(notFoundHandler()).use(errorHandler(deps.logger));

afterAll(() => {
  deps.db.close();
});

describe("GET /versions", () => {
  it("devuelve la version partida con el total y la paginacion por defecto", async () => {
    const res = await request(app).get("/versions");
    const body = res.body as PageBody<VersioBody>;
    expect(res.status).toBe(200);
    expect(body.total).toBe(1);
    expect(body.limit).toBe(100);
    expect(body.offset).toBe(0);
    expect(body.items).toHaveLength(1);
    expect(body.items[0]).toMatchObject({ id: 1, nom: "partida", idVersioReferencia: null, veredicte: null });
  });

  it("VersioDto tiene exactamente las claves del contrato y nunca el informe", async () => {
    const res = await request(app).get("/versions");
    const item = (res.body as PageBody<VersioBody>).items[0];
    expect(Object.keys(item ?? {}).sort()).toEqual(
      ["creadaEl", "id", "idEscenari", "idVersioReferencia", "mode", "nom", "semestre", "veredicte"].sort(),
    );
    expect(typeof item?.creadaEl).toBe("string");
    expect(["complet", "nomes_aules"]).toContain(item?.mode);
    expect(res.text).not.toMatch(/informe/i);
  });

  it("respeta limit y offset sin alterar el total", async () => {
    const res = await request(app).get("/versions").query({ limit: 1, offset: 1 });
    const body = res.body as PageBody<VersioBody>;
    expect(res.status).toBe(200);
    expect(body.items).toEqual([]);
    expect(body.total).toBe(1);
    expect(body.limit).toBe(1);
    expect(body.offset).toBe(1);
  });

  it.each([
    ["limit", 0],
    ["limit", 501],
    ["limit", "abc"],
    ["offset", -1],
    ["offset", SENTINELLA],
  ])("%s=%s responde 400 sin eco del valor", async (clau, valor) => {
    const res = await request(app)
      .get("/versions")
      .query({ [clau]: valor });
    expect(res.status).toBe(400);
    expect((res.body as ErrorBody).error).toBe("invalid_request");
    expect(JSON.stringify(res.body)).not.toContain(SENTINELLA);
  });
});

describe("GET /versions/:id/assignacions", () => {
  it("lista las 28 asignaciones ordenadas por idSessio ASC", async () => {
    const res = await request(app).get("/versions/1/assignacions");
    const body = res.body as PageBody<AssignacioBody>;
    expect(res.status).toBe(200);
    expect(body.total).toBe(28);
    expect(body.limit).toBe(100);
    expect(body.offset).toBe(0);
    const ids = body.items.map((a) => a.idSessio);
    // proposta_partida.csv: S90001..S90028 consecutivos
    expect(ids).toEqual(Array.from({ length: 28 }, (_, i) => `S${String(90001 + i)}`));
  });

  it("cada item tiene exactamente {idSessio, dia, hIni, aula, data}", async () => {
    const res = await request(app).get("/versions/1/assignacions");
    const body = res.body as PageBody<AssignacioBody>;
    for (const item of body.items) {
      expect(Object.keys(item).sort()).toEqual(["aula", "data", "dia", "hIni", "idSessio"]);
    }
    expect(body.items[0]).toEqual({ idSessio: "S90001", dia: "X", hIni: "10:00", aula: "Q7/7101", data: null });
    expect(body.items.find((a) => a.idSessio === "S90005")).toEqual({
      idSessio: "S90005",
      dia: "L",
      hIni: "08:30",
      aula: "Q8/8103",
      data: null,
    });
    expect(body.items.find((a) => a.idSessio === "S90017")?.aula).toBe("J/012");
  });

  it("las 4 asignaciones sin aula salen con aula null (no cadena vacia)", async () => {
    const res = await request(app).get("/versions/1/assignacions");
    const body = res.body as PageBody<AssignacioBody>;
    const senseAula = body.items.filter((a) => a.aula === null).map((a) => a.idSessio);
    expect(senseAula).toEqual(["S90021", "S90022", "S90025", "S90026"]);
    expect(body.items.filter((a) => a.aula === "")).toHaveLength(0);
    expect(body.items.filter((a) => a.aula !== null)).toHaveLength(24);
  });

  it("limit y offset paginan sin alterar el total", async () => {
    const res = await request(app).get("/versions/1/assignacions").query({ limit: 5, offset: 20 });
    const body = res.body as PageBody<AssignacioBody>;
    expect(res.status).toBe(200);
    expect(body.items.map((a) => a.idSessio)).toEqual(["S90021", "S90022", "S90023", "S90024", "S90025"]);
    expect(body.total).toBe(28);
    expect(body.limit).toBe(5);
    expect(body.offset).toBe(20);
  });

  it("offset al final devuelve la ultima pagina parcial", async () => {
    const res = await request(app).get("/versions/1/assignacions").query({ limit: 10, offset: 25 });
    const body = res.body as PageBody<AssignacioBody>;
    expect(body.items.map((a) => a.idSessio)).toEqual(["S90026", "S90027", "S90028"]);
  });

  it.each(["abc", "0", "-1", "1.5", SENTINELLA])("id=%s responde 400 sin eco del valor", async (id) => {
    const res = await request(app).get(`/versions/${id}/assignacions`);
    expect(res.status).toBe(400);
    expect((res.body as ErrorBody).error).toBe("invalid_request");
    expect(JSON.stringify(res.body)).not.toContain(SENTINELLA);
  });

  it("version inexistente responde 404 not_found", async () => {
    const res = await request(app).get("/versions/999/assignacions");
    expect(res.status).toBe(404);
    expect(res.body).toEqual({ error: "not_found" });
  });

  it.each([
    ["limit", 0],
    ["limit", 501],
    ["offset", -1],
  ])("%s=%s responde 400", async (clau, valor) => {
    const res = await request(app)
      .get("/versions/1/assignacions")
      .query({ [clau]: valor });
    expect(res.status).toBe(400);
    expect((res.body as ErrorBody).error).toBe("invalid_request");
  });

  it("un id con SQL se rechaza con 400 y nunca 500", async () => {
    const res = await request(app).get(`/versions/${encodeURIComponent("1 OR 1=1")}/assignacions`);
    expect(res.status).toBe(400);
  });
});
