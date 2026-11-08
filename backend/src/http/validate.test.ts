import { describe, expect, it } from "vitest";
import { z } from "zod";
import { ValidationError } from "../domain/errors.js";
import { parseParams, parseQuery } from "./validate.js";

const SECRET = "ZZ_VALOR_9";
const querySchema = z.object({ n: z.coerce.number().int().min(1), tipus: z.enum(["a", "b"]).optional() });
const paramsSchema = z.object({ id: z.coerce.number().int().positive() });

function validationErrorOf(fn: () => unknown): ValidationError {
  try {
    fn();
  } catch (error) {
    if (error instanceof ValidationError) return error;
    throw error;
  }
  throw new Error("no lanzó");
}

describe("parseQuery", () => {
  it("devuelve el valor tipado", () => {
    const value: { n: number; tipus?: "a" | "b" | undefined } = parseQuery(querySchema, { n: "3", tipus: "a" });
    expect(value).toEqual({ n: 3, tipus: "a" });
  });

  it("lanza ValidationError nombrando el campo sin incluir el valor", () => {
    const error = validationErrorOf(() => parseQuery(querySchema, { n: SECRET }));
    expect(error.issues.length).toBeGreaterThan(0);
    expect(error.issues.map((i) => i.path)).toContain("n");
    expect(JSON.stringify(error.issues)).not.toContain(SECRET);
    expect(error.message).not.toContain(SECRET);
  });

  it("no revela el valor de un enum inválido", () => {
    const error = validationErrorOf(() => parseQuery(querySchema, { n: "1", tipus: SECRET }));
    expect(error.issues.map((i) => i.path)).toContain("tipus");
    expect(JSON.stringify(error.issues)).not.toContain(SECRET);
  });

  it("lanza ValidationError si la query no es un objeto", () => {
    expect(() => parseQuery(querySchema, undefined)).toThrow(ValidationError);
  });
});

describe("parseParams", () => {
  it("devuelve el valor tipado", () => {
    const value: { id: number } = parseParams(paramsSchema, { id: "42" });
    expect(value).toEqual({ id: 42 });
  });

  it("lanza ValidationError nombrando el campo sin incluir el valor", () => {
    const error = validationErrorOf(() => parseParams(paramsSchema, { id: SECRET }));
    expect(error.issues.map((i) => i.path)).toContain("id");
    expect(JSON.stringify(error.issues)).not.toContain(SECRET);
  });

  it.each(["0", "-3", "1.5"])("rechaza id=%j", (id) => {
    expect(() => parseParams(paramsSchema, { id })).toThrow(ValidationError);
  });
});

describe("issues custom", () => {
  it("usa el mensaje propio del refine, sin el valor", () => {
    const schema = z.object({ a: z.string().refine((v) => v === "ok", { message: "debe ser ok" }) });
    const error = validationErrorOf(() => parseQuery(schema, { a: SECRET }));
    expect(error.issues).toEqual([{ path: "a", message: "debe ser ok" }]);
  });
});
