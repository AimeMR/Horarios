import { describe, expect, it } from "vitest";
import { paginationSchema } from "./pagination.js";

describe("paginationSchema", () => {
  it("aplica limit 100 y offset 0 por defecto", () => {
    expect(paginationSchema.parse({})).toEqual({ limit: 100, offset: 0 });
  });

  it("convierte strings a números", () => {
    expect(paginationSchema.parse({ limit: "25", offset: "50" })).toEqual({ limit: 25, offset: 50 });
  });

  it.each([1, 500, "1", "500"])("acepta limit=%j", (limit) => {
    expect(paginationSchema.safeParse({ limit }).success).toBe(true);
  });

  it.each([0, 501, -1, "abc", "1.5", 1.5, "0", "501"])("rechaza limit=%j", (limit) => {
    expect(paginationSchema.safeParse({ limit }).success).toBe(false);
  });

  it.each([0, "0", 10000])("acepta offset=%j", (offset) => {
    expect(paginationSchema.safeParse({ offset }).success).toBe(true);
  });

  it.each([-1, "-1", "abc", "2.5"])("rechaza offset=%j", (offset) => {
    expect(paginationSchema.safeParse({ offset }).success).toBe(false);
  });
});
