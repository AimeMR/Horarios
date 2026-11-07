import { describe, expect, it } from "vitest";
import { dataMateixaSetmana, diesDeSetmana, dillunsDeSetmana, hora, minuts } from "./setmana.js";

describe("dillunsDeSetmana", () => {
  it.each([
    ["2026-W38", "2026-09-14"],
    ["2026-W01", "2025-12-29"],
    ["2027-W02", "2027-01-11"],
    ["2026-W53", "2026-12-28"],
    ["2020-W53", "2020-12-28"],
  ])("%s comença el %s", (setmana, esperat) => {
    expect(dillunsDeSetmana(setmana)).toBe(esperat);
  });

  it.each(["2027-W53", "2026-W00", "2026-W54", "2026-38", "26-W38", "2026-W3", "", "2026-W38 "])(
    "rebutja %j",
    (setmana) => {
      expect(() => dillunsDeSetmana(setmana)).toThrow(RangeError);
    },
  );
});

describe("diesDeSetmana", () => {
  it("dona dilluns a divendres amb la seva data", () => {
    expect(diesDeSetmana("2026-W38")).toEqual([
      { dia: "L", data: "2026-09-14" },
      { dia: "M", data: "2026-09-15" },
      { dia: "X", data: "2026-09-16" },
      { dia: "J", data: "2026-09-17" },
      { dia: "V", data: "2026-09-18" },
    ]);
  });

  it("travessa el canvi d'any", () => {
    expect(diesDeSetmana("2026-W53").at(-1)).toEqual({ dia: "V", data: "2027-01-01" });
  });
});

describe("dataMateixaSetmana", () => {
  it("avança i recula dins la setmana", () => {
    expect(dataMateixaSetmana("2026-09-16", "X", "V")).toBe("2026-09-18");
    expect(dataMateixaSetmana("2026-09-16", "X", "L")).toBe("2026-09-14");
    expect(dataMateixaSetmana("2026-09-16", "X", "X")).toBe("2026-09-16");
  });

  it("rebutja una data mal formada o inexistent", () => {
    expect(() => dataMateixaSetmana("2026-02-30", "L", "M")).toThrow(RangeError);
    expect(() => dataMateixaSetmana("16/09/2026", "L", "M")).toThrow(RangeError);
  });
});

describe("minuts i hora", () => {
  it("converteixen en els dos sentits", () => {
    expect(minuts("08:30")).toBe(510);
    expect(minuts("21:00")).toBe(1260);
    expect(hora(510)).toBe("08:30");
    expect(hora(510 + 90)).toBe("10:00");
  });

  it.each(["8:30", "24:00", "08:60", "08-30", ""])("minuts rebutja %j", (valor) => {
    expect(() => minuts(valor)).toThrow(RangeError);
  });

  it.each([-1, 1440, 1.5])("hora rebutja %d", (valor) => {
    expect(() => hora(valor)).toThrow(RangeError);
  });
});
