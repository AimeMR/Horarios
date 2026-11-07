import { Writable } from "node:stream";
import express from "express";
import pino from "pino";
import request from "supertest";
import { beforeEach, describe, expect, it } from "vitest";
import { NotFoundError, NotImplementedError, ValidationError } from "../domain/errors.js";
import { errorHandler, notFoundHandler } from "./errors.js";

const SECRET_MESSAGE = "ZZ_SECRETO_INTERNO_7";
const SECRET_BODY = "ZZ_CUERPO_PETICION_5";
const SECRET_VALUE = "ZZ_VALOR_9";

let logLines: string[] = [];

function memoryLogger(): pino.Logger {
  const stream = new Writable({
    write(chunk: Buffer, _encoding, callback) {
      logLines.push(chunk.toString());
      callback();
    },
  });
  return pino({ level: "debug" }, stream);
}

function buildApp(): express.Express {
  const app = express();
  app.use(express.json());
  app.use((_req, res, next) => {
    res.setHeader("x-request-id", "req-fijo-123");
    next();
  });
  app.get("/not-found", () => {
    throw new NotFoundError("falta");
  });
  app.get("/validation", () => {
    throw new ValidationError([{ path: "limit", message: "debe ser <= 500" }]);
  });
  app.get("/not-implemented", () => {
    throw new NotImplementedError("pendiente");
  });
  app.get("/boom", () => {
    throw new Error(SECRET_MESSAGE);
  });
  app.post("/boom", () => {
    throw new Error(SECRET_MESSAGE);
  });
  app.get("/async-boom", async () => {
    await Promise.resolve();
    throw new Error(SECRET_MESSAGE);
  });
  app.get("/async-not-found", async () => {
    await Promise.resolve();
    throw new NotFoundError("falta async");
  });
  app.get("/p/:id", () => {
    throw new Error("no debería llegar");
  });
  app.get("/forbidden", () => {
    throw Object.assign(new Error(SECRET_MESSAGE), { status: 403 });
  });
  app.use(notFoundHandler());
  app.use(errorHandler(memoryLogger()));
  return app;
}

beforeEach(() => {
  logLines = [];
});

describe("notFoundHandler", () => {
  it("responde 404 { error: not_found } en rutas desconocidas", async () => {
    const response = await request(buildApp()).get("/no-existe");
    expect(response.status).toBe(404);
    expect(response.body).toEqual({ error: "not_found" });
  });
});

describe("errorHandler", () => {
  it("NotFoundError -> 404 not_found sin el mensaje interno", async () => {
    const response = await request(buildApp()).get("/not-found");
    expect(response.status).toBe(404);
    expect(response.body).toEqual({ error: "not_found" });
  });

  it("ValidationError -> 400 con issues (ruta y mensaje)", async () => {
    const response = await request(buildApp()).get("/validation");
    expect(response.status).toBe(400);
    expect(response.body).toEqual({
      error: "invalid_request",
      issues: [{ path: "limit", message: "debe ser <= 500" }],
    });
  });

  it("ValidationError no filtra el valor recibido", async () => {
    const app = express();
    app.get("/v", () => {
      throw new ValidationError([{ path: "n", message: "debe ser entero" }]);
    });
    app.use(errorHandler(memoryLogger()));
    const response = await request(app).get("/v").query({ n: SECRET_VALUE });
    expect(response.status).toBe(400);
    expect(response.text).not.toContain(SECRET_VALUE);
  });

  it("NotImplementedError -> 501 not_implemented", async () => {
    const response = await request(buildApp()).get("/not-implemented");
    expect(response.status).toBe(501);
    expect(response.body).toEqual({ error: "not_implemented" });
  });

  it("error genérico -> 500 internal_error con requestId, sin mensaje ni pila", async () => {
    const response = await request(buildApp()).get("/boom");
    expect(response.status).toBe(500);
    const body = response.body as { error: string; requestId: unknown };
    expect(body.error).toBe("internal_error");
    expect(typeof body.requestId).toBe("string");
    expect((body.requestId as string).length).toBeGreaterThan(0);
    expect(Object.keys(body).sort()).toEqual(["error", "requestId"]);
    expect(response.text).not.toContain(SECRET_MESSAGE);
    expect(response.text).not.toContain("at ");
    expect(response.text).not.toContain(".ts");
  });

  it("errores async también llegan al handler (Express 5)", async () => {
    const app = buildApp();
    const generic = await request(app).get("/async-boom");
    expect(generic.status).toBe(500);
    expect(generic.body).toMatchObject({ error: "internal_error" });
    expect(generic.text).not.toContain(SECRET_MESSAGE);

    const notFound = await request(app).get("/async-not-found");
    expect(notFound.status).toBe(404);
    expect(notFound.body).toEqual({ error: "not_found" });
  });

  it("JSON mal formado -> 400 invalid_request", async () => {
    const response = await request(buildApp())
      .post("/boom")
      .set("Content-Type", "application/json")
      .send("{ no es json");
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
  });

  it("registra el error interno en el log pero no el cuerpo de la petición", async () => {
    const response = await request(buildApp()).post("/boom").send({ secreto: SECRET_BODY });
    expect(response.status).toBe(500);
    const logged = logLines.join("\n");
    expect(logged).toContain(SECRET_MESSAGE);
    expect(logged).not.toContain(SECRET_BODY);
  });

  it("el log del error incluye el requestId devuelto al cliente", async () => {
    const response = await request(buildApp()).get("/boom");
    const { requestId } = response.body as { requestId: string };
    expect(logLines.join("\n")).toContain(requestId);
  });

  it("parámetro con codificación inválida -> 400 invalid_request sin registrar el valor crudo", async () => {
    const response = await request(buildApp()).get("/p/%E0");
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
    const logged = logLines.join("\n");
    expect(logged).not.toContain("%E0");
    expect(logged).not.toContain("decode");
  });

  it("cualquier error 4xx ajeno al dominio -> 400 invalid_request sin su mensaje", async () => {
    const response = await request(buildApp()).get("/forbidden");
    expect(response.status).toBe(400);
    expect(response.body).toEqual({ error: "invalid_request" });
    expect(logLines.join("\n")).not.toContain(SECRET_MESSAGE);
  });
});
