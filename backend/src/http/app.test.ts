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
const HOST = "127.0.0.1:3000";

afterAll(() => {
  db.close();
});

describe("createApp", () => {
  it("GET /health -> 200 { status: ok }", async () => {
    const response = await request(app).get("/health").set("Host", HOST);
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: "ok" });
  });

  it("ruta inexistente -> 404 { error: not_found }", async () => {
    const response = await request(app).get("/no-existe").set("Host", HOST);
    expect(response.status).toBe(404);
    expect(response.body).toEqual({ error: "not_found" });
  });

  it("aplica cabeceras de helmet y oculta x-powered-by", async () => {
    const response = await request(app).get("/health").set("Host", HOST);
    expect(response.headers["x-content-type-options"]).toBe("nosniff");
    expect(response.headers["x-powered-by"]).toBeUndefined();
  });

  it("devuelve x-request-id y es distinto en cada petición", async () => {
    const first = await request(app).get("/health").set("Host", HOST);
    const second = await request(app).get("/health").set("Host", HOST);
    const a = first.headers["x-request-id"];
    const b = second.headers["x-request-id"];
    expect(typeof a).toBe("string");
    expect(a).not.toBe("");
    expect(a).not.toBe(b);
  });

  it("CORS: el origen configurado recibe access-control-allow-origin", async () => {
    const response = await request(app).get("/health").set("Host", HOST).set("Origin", config.corsOrigin);
    expect(response.headers["access-control-allow-origin"]).toBe(config.corsOrigin);
    expect(response.headers["access-control-allow-credentials"]).toBeUndefined();
  });

  it("CORS: otro origen no recibe access-control-allow-origin", async () => {
    const response = await request(app).get("/health").set("Host", HOST).set("Origin", "https://evil.example");
    expect(response.headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("POST con JSON mal formado -> 400 invalid_request", async () => {
    const response = await request(app)
      .post("/health")
      .set("Host", HOST)
      .set("Content-Type", "application/json")
      .send('{"a": ');
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
  });

  it("cuerpo de más de 100 kb -> 400 invalid_request", async () => {
    const response = await request(app)
      .post("/health")
      .set("Host", HOST)
      .set("Content-Type", "application/json")
      .send(JSON.stringify({ blob: "x".repeat(101 * 1024) }));
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
  });

  it("cuerpo JSON pequeño no da error de parseo", async () => {
    const response = await request(app).post("/health").set("Host", HOST).send({ a: 1 });
    expect(response.status).not.toBe(400);
  });

  it.each(["127.0.0.1:3000", "localhost:3000", "[::1]:3000"])("Host %s -> 200", async (host) => {
    const response = await request(app).get("/health").set("Host", host);
    expect(response.status).toBe(200);
  });

  it.each(["evil.example", "evil.example:3000", "127.0.0.1:4000", "localhost", "127.0.0.1.evil.example:3000"])(
    "Host %s -> 403 invalid_request (DNS rebinding)",
    async (host) => {
      const response = await request(app).get("/health").set("Host", host);
      expect(response.status).toBe(403);
      expect(response.body).toEqual({ error: "invalid_request" });
    },
  );

  it("acepta el host configurado si no es loopback", async () => {
    const lan = createApp({
      db,
      config: { ...config, host: "192.168.1.5" },
      logger: createLogger("silent"),
    });
    const ok = await request(lan).get("/health").set("Host", "192.168.1.5:3000");
    expect(ok.status).toBe(200);
    const bad = await request(lan).get("/health").set("Host", "evil.example:3000");
    expect(bad.status).toBe(403);
  });
});
