import { describe, expect, it } from "vitest";
import { informeGuardatSchema } from "./informe.dto.js";

const comptes = { total: 1, compten: 0, declarades: 0, heretades: 0 };

function informeAmb(restriccions: Record<string, unknown>, noAvaluables: Record<string, unknown>): unknown {
  return {
    restriccions,
    no_avaluables: noAvaluables,
    objectius: {
      hores_mortes_min: 0,
      desplacaments_aula: 0,
      desplacaments_edifici: 0,
      canvis_franja: 0,
      canvis_aula: 0,
      r6_aules_te_extra_per_grup: 0,
      r6_canvis_te_paul_fora_passadis: 0,
      sessions_avaluades: 0,
    },
    relaxacions_declarades: 0,
    incompliments_declarats: 0,
    context: { semestre: null, nomes_aules: false },
  };
}

describe("informeGuardatSchema: claus de les regles", () => {
  it("accepta regles amb el format Rn-NOM", () => {
    const result = informeGuardatSchema.safeParse(
      informeAmb({ "R3-AULA": comptes, "R10-X1": comptes }, { "R9-NOVA": 2 }),
    );
    expect(result.success).toBe(true);
  });

  it.each(["", "r3-aula", "R3_AULA", "R123-A", `R3-${"A".repeat(33)}`, "R3-A B", "<script>"])(
    "rebutja la clau %j a restriccions",
    (clau) => {
      expect(informeGuardatSchema.safeParse(informeAmb({ [clau]: comptes }, {})).success).toBe(false);
    },
  );

  it("rebutja una clau invàlida a no_avaluables", () => {
    expect(informeGuardatSchema.safeParse(informeAmb({}, { "no-regla": 1 })).success).toBe(false);
  });

  it("rebutja més de 100 entrades", () => {
    const molts = Object.fromEntries(Array.from({ length: 101 }, (_, i) => [`R1-X${String(i)}`, 1]));
    const moltesRestriccions = Object.fromEntries(
      Array.from({ length: 101 }, (_, i) => [`R1-X${String(i)}`, comptes]),
    );
    expect(informeGuardatSchema.safeParse(informeAmb({}, molts)).success).toBe(false);
    expect(informeGuardatSchema.safeParse(informeAmb(moltesRestriccions, {})).success).toBe(false);
  });
});
