import { describe, expect, it } from "vitest";
import { franges, minutsUnio, percentatge, solapa } from "./ocupacio.js";

const m = (h: number, min = 0): number => h * 60 + min;

describe("minutsUnio", () => {
  it("suma intervals disjunts", () => {
    expect(minutsUnio([{ ini: m(9), fi: m(10) }, { ini: m(12), fi: m(13, 30) }])).toBe(150);
  });

  it("no suma dues vegades un solapament", () => {
    expect(minutsUnio([{ ini: m(10), fi: m(11, 30) }, { ini: m(10, 30), fi: m(12) }])).toBe(120);
  });

  it("uneix intervals adjacents i contiguts dins d'un altre", () => {
    expect(minutsUnio([{ ini: m(9), fi: m(10) }, { ini: m(10), fi: m(11) }])).toBe(120);
    expect(minutsUnio([{ ini: m(9), fi: m(12) }, { ini: m(10), fi: m(11) }])).toBe(180);
  });

  it("retalla abans de 08:30 i despres de 21:00", () => {
    expect(minutsUnio([{ ini: m(8), fi: m(9) }])).toBe(30);
    expect(minutsUnio([{ ini: m(20, 30), fi: m(22) }])).toBe(30);
    expect(minutsUnio([{ ini: m(6), fi: m(7) }, { ini: m(22), fi: m(23) }])).toBe(0);
  });

  it("buit -> 0", () => {
    expect(minutsUnio([])).toBe(0);
  });
});

describe("franges i solapa", () => {
  it("13 franges, la darrera 20:30-21:00", () => {
    const f = franges();
    expect(f).toHaveLength(13);
    expect(f[0]).toEqual({ hora: "08:30", ini: m(8, 30), fi: m(9, 30) });
    expect(f[12]).toEqual({ hora: "20:30", ini: m(20, 30), fi: m(21) });
  });

  it("intervals semioberts: tocar-se no es solapar", () => {
    expect(solapa({ ini: m(9), fi: m(10) }, { ini: m(10), fi: m(11) })).toBe(false);
    expect(solapa({ ini: m(9), fi: m(10, 1) }, { ini: m(10), fi: m(11) })).toBe(true);
  });
});

describe("percentatge", () => {
  it("arrodoneix a un decimal", () => {
    expect(percentatge(270, 3750)).toBe(7.2);
    expect(percentatge(90, 3750)).toBe(2.4);
    expect(percentatge(210, 3750)).toBe(5.6);
    expect(percentatge(0, 3750)).toBe(0);
    expect(percentatge(1, 3)).toBe(33.3);
  });
});
