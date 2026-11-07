import Database from "better-sqlite3";
import request from "supertest";
import { afterAll, describe, expect, it } from "vitest";
import type { Config } from "../config.js";
import { createApp } from "./app.js";
import { createLogger } from "./logger.js";

const config: Config = {
  dbPath: ":memory:",
  host: "127.0.0.1",
  port: 3000,
  corsOrigin: "http://localhost:5173",
  logLevel: "silent",
};

const db = new Database(":memory:");
const app = createApp({ db, config, logger: createLogger("silent") });

afterAll(() => {
  db.close();
});

describe("createApp", () => {
  it("GET /health -> 200 { status: ok }", async () => {
    const response = await request(app).get("/health");
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: "ok" });
  });

  it("ruta inexistente -> 404 { error: not_found }", async () => {
    const response = await request(app).get("/no-existe");
    expect(response.status).toBe(404);
    expect(response.body).toEqual({ error: "not_found" });
  });

  it("aplica cabeceras de helmet y oculta x-powered-by", async () => {
    const response = await request(app).get("/health");
    expect(response.headers["x-content-type-options"]).toBe("nosniff");
    expect(response.headers["x-powered-by"]).toBeUndefined();
  });

  it("devuelve x-request-id y es distinto en cada petición", async () => {
    const first = await request(app).get("/health");
    const second = await request(app).get("/health");
    const a = first.headers["x-request-id"];
    const b = second.headers["x-request-id"];
    expect(typeof a).toBe("string");
    expect(a).not.toBe("");
    expect(a).not.toBe(b);
  });

  it("CORS: el origen configurado recibe access-control-allow-origin", async () => {
    const response = await request(app).get("/health").set("Origin", config.corsOrigin);
    expect(response.headers["access-control-allow-origin"]).toBe(config.corsOrigin);
    expect(response.headers["access-control-allow-credentials"]).toBeUndefined();
  });

  it("CORS: otro origen no recibe access-control-allow-origin", async () => {
    const response = await request(app).get("/health").set("Origin", "https://evil.example");
    expect(response.headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("POST con JSON mal formado -> 400 invalid_request", async () => {
    const response = await request(app)
      .post("/health")
      .set("Content-Type", "application/json")
      .send('{"a": ');
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
  });

  it("cuerpo de más de 100 kb -> 400 invalid_request", async () => {
    const response = await request(app)
      .post("/health")
      .set("Content-Type", "application/json")
      .send(JSON.stringify({ blob: "x".repeat(101 * 1024) }));
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
  });

  it("cuerpo JSON pequeño no da error de parseo", async () => {
    const response = await request(app).post("/health").send({ a: 1 });
    expect(response.status).not.toBe(400);
  });
});
