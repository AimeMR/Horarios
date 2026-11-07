import express from "express";
import request from "supertest";
import { describe, expect, it } from "vitest";
import { healthRouter } from "./health.controller.js";

function appWithHealth(): express.Express {
  const app = express();
  app.use("/health", healthRouter());
  return app;
}

describe("healthRouter", () => {
  it("responde 200 con { status: ok }", async () => {
    const response = await request(appWithHealth()).get("/health");
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ status: "ok" });
  });

  it("no revela versión, ruta de la BD ni otros datos", async () => {
    const response = await request(appWithHealth()).get("/health");
    const text = response.text.toLowerCase();
    expect(Object.keys(response.body as Record<string, unknown>)).toEqual(["status"]);
    expect(text).not.toContain("version");
    expect(text).not.toContain(".db");
    expect(text).not.toContain("sqlite");
  });

  it("no acepta escrituras", async () => {
    const response = await request(appWithHealth()).post("/health").send({});
    expect(response.status).not.toBe(200);
  });
});
