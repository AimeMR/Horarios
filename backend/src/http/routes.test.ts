import request from "supertest";
import { afterAll, describe, expect, it } from "vitest";
import { testDeps } from "../../test/helpers.js";
import { createApp } from "./app.js";

// Integración: cada feature queda montada en su ruta a través de createApp + registerRoutes.
const deps = testDeps();
const app = createApp(deps);
// La app solo acepta Host de loopback en el puerto configurado (protección contra DNS rebinding).
const host = `localhost:${deps.config.port}`;
const get = (ruta: string): request.Test => request(app).get(ruta).set("Host", host);

afterAll(() => {
  deps.db.close();
});

describe("registerRoutes", () => {
  it.each([
    ["/health", 200],
    ["/aules", 200],
    ["/versions", 200],
    ["/versions/1/assignacions", 200],
    ["/versions/1/informe", 200],
    ["/versions/1/parrilla?setmana=2026-W38&cohort=GFA:1r", 200],
    ["/versions/1/ocupacio?setmana=2026-W38", 200],
    ["/versions/999/informe", 404],
    ["/versions/999/parrilla?setmana=2026-W38&aula=Q7/7101", 404],
    ["/versions/999/ocupacio?setmana=2026-W38", 404],
    ["/versions/abc/assignacions", 400],
    ["/versions/1/parrilla?setmana=2026-W38", 400],
    ["/versions/1/desconegut", 404],
  ])("GET %s -> %d", async (ruta, estat) => {
    const response = await get(ruta);
    expect(response.status).toBe(estat);
    expect(response.headers["x-request-id"]).toBeTypeOf("string");
  });

  it("un Host ajeno recibe 403 (DNS rebinding)", async () => {
    const response = await request(app).get("/versions").set("Host", "evil.example:3000");
    expect(response.status).toBe(403);
  });

  it("la parrilla y la ocupación responden con los datos de la fixture", async () => {
    const parrilla = await get("/versions/1/parrilla?setmana=2026-W38&cohort=GFA:1r");
    expect((parrilla.body as { items: { idSessio: string }[] }).items.map((i) => i.idSessio)).toEqual([
      "S90005",
      "S90013",
      "S90009",
      "S90001",
      "S90015",
      "S90003",
    ]);
    const ocupacio = await get("/versions/1/ocupacio?setmana=2026-W38");
    expect((ocupacio.body as { perFranja: unknown[] }).perFranja).toHaveLength(65);
  });
});
