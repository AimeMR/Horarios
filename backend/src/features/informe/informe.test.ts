import express from "express";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openWritableCopy, testDeps } from "../../../test/helpers.js";
import type { AppDeps } from "../../http/app.js";
import { errorHandler, notFoundHandler } from "../../http/errors.js";
import { informeRouter } from "./informe.controller.js";

interface RestriccioBody {
  regla: string;
  total: number;
  compten: number;
  declarades: number;
  heretades: number;
  estat: string;
}
interface InformeBody {
  restriccions: RestriccioBody[];
  noAvaluables: { regla: string; sessions: number }[];
  objectius: Record<string, number | null>;
  relaxacionsDeclarades: number;
  incomplimentsDeclarats: number;
  context: Record<string, unknown>;
}
interface RespostaBody {
  idVersio: number;
  nom: string;
  veredicte: string | null;
  informe: InformeBody | null;
}

const SENTINELLA = "ZZ_VALOR_9";
const CONTINGUT_PRIVAT = "ZZ_CONTINGUT_PRIVAT_9";

// Las 20 reglas del contrato, en orden.
const REGLES = [
  "R0-FORMAT",
  "R0-HORARI",
  "R1-FIXADA",
  "R1-TORN",
  "R2-FINESTRA",
  "R2-CALENDARI",
  "R3-AULA",
  "R3-AFORAMENT",
  "R3-TIPUS",
  "R3-TANCADA",
  "R4-AULA",
  "R4-DOCENT",
  "R4-ALUMNAT",
  "R4-PLAB",
  "R4-COMPARTIDA",
  "R5-FALTA",
  "R5-SENSE-AULA",
  "R5-RECUPERACIO",
  "R7-PLAB",
  "R8-RESERVA",
];

const informeComplet = {
  veredicte: "VALIDA AMB RELAXACIONS DECLARADES",
  restriccions: {
    "R3-AULA": { total: 1, compten: 0, declarades: 0, heretades: 1 }, // OK
    "R1-TORN": { total: 5, compten: 2, declarades: 1, heretades: 0 }, // KO (compten > 0 gana a declarades)
    "R2-FINESTRA": { total: 3, compten: 0, declarades: 2, heretades: 1 }, // REL
    "R8-RESERVA": { total: 0, compten: 0, declarades: 0, heretades: 0 }, // OK explicito
  },
  no_avaluables: { "R4-PLAB": 2, "R1-TORN": 3, "R0-FORMAT": 1 },
  objectius: {
    hores_mortes_min: 120,
    desplacaments_aula: 7,
    desplacaments_edifici: 3,
    canvis_franja: 4,
    canvis_aula: 5,
    r6_aules_te_extra_per_grup: 2,
    r6_canvis_te_paul_fora_passadis: 6,
    sessions_avaluades: 28,
    canvis_franja_vs_referencia: 9,
    canvis_aula_vs_referencia: 0,
  },
  relaxacions_declarades: 3,
  incompliments_declarats: 1,
  context: {
    semestre: 1,
    nomes_aules: true,
    escenari: "C:\\secret\\path",
    paquet_sha256: "a".repeat(64),
    sessions_sha256: "b".repeat(64),
  },
  extra_desconegut: CONTINGUT_PRIVAT,
};

const informeRegleDesconeguda = {
  veredicte: "NO VALIDA",
  restriccions: {
    "R9-NOVA": { total: 2, compten: 1, declarades: 0, heretades: 0 },
    "R9-ALFA": { total: 1, compten: 0, declarades: 1, heretades: 0 },
    "R1-TORN": { total: 1, compten: 0, declarades: 0, heretades: 0 },
  },
  no_avaluables: {},
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

const informeForaDeEsquema = { restriccions: `${CONTINGUT_PRIVAT} no es un objeto`, objectius: 5 };

let deps: AppDeps;
let base: AppDeps;
let writable: ReturnType<typeof openWritableCopy>;
let app: express.Express;
let idComplet = 0;
let idDesconeguda = 0;
let idInvalid = 0;

function inserir(nom: string, veredicte: string | null, informe: unknown): number {
  const info = writable.db
    .prepare("INSERT INTO versio_horari (nom, veredicte, informe_json) VALUES (?, ?, ?)")
    .run(nom, veredicte, JSON.stringify(informe));
  return Number(info.lastInsertRowid);
}

beforeAll(() => {
  writable = openWritableCopy();
  idComplet = inserir("informe-complet", "VALIDA AMB RELAXACIONS DECLARADES", informeComplet);
  idDesconeguda = inserir("informe-regla-nova", "NO VALIDA", informeRegleDesconeguda);
  idInvalid = inserir("informe-invalid", null, informeForaDeEsquema);
  base = testDeps();
  deps = { ...base, db: writable.db };
  app = express().use("/versions", informeRouter(deps)).use(notFoundHandler()).use(errorHandler(deps.logger));
});

afterAll(() => {
  base.db.close();
  writable.dispose();
});

async function informe(id: number | string): Promise<{ status: number; body: RespostaBody; text: string }> {
  const res = await request(app).get(`/versions/${String(id)}/informe`);
  return { status: res.status, body: res.body as RespostaBody, text: res.text };
}

describe("GET /versions/:id/informe", () => {
  describe("version sin verificar", () => {
    it("devuelve 200 con veredicte null e informe null", async () => {
      const { status, body } = await informe(1);
      expect(status).toBe(200);
      expect(body).toEqual({ idVersio: 1, nom: "partida", veredicte: null, informe: null });
    });
  });

  describe("informe valido", () => {
    it("devuelve cabecera con idVersio, nom y veredicte", async () => {
      const { status, body } = await informe(idComplet);
      expect(status).toBe(200);
      expect(body.idVersio).toBe(idComplet);
      expect(body.nom).toBe("informe-complet");
      expect(body.veredicte).toBe("VALIDA AMB RELAXACIONS DECLARADES");
    });

    it("lista las 20 reglas en el orden del contrato, sin extras", async () => {
      const { body } = await informe(idComplet);
      expect(body.informe?.restriccions.map((r) => r.regla)).toEqual(REGLES);
    });

    it("calcula estat KO, REL y OK y copia los contadores", async () => {
      const { body } = await informe(idComplet);
      const per = (regla: string): RestriccioBody | undefined =>
        body.informe?.restriccions.find((r) => r.regla === regla);
      expect(per("R1-TORN")).toEqual({
        regla: "R1-TORN",
        total: 5,
        compten: 2,
        declarades: 1,
        heretades: 0,
        estat: "KO",
      });
      expect(per("R2-FINESTRA")).toEqual({
        regla: "R2-FINESTRA",
        total: 3,
        compten: 0,
        declarades: 2,
        heretades: 1,
        estat: "REL",
      });
      expect(per("R3-AULA")).toEqual({
        regla: "R3-AULA",
        total: 1,
        compten: 0,
        declarades: 0,
        heretades: 1,
        estat: "OK",
      });
    });

    it("las reglas ausentes salen con ceros y OK", async () => {
      const { body } = await informe(idComplet);
      const ausents = (body.informe?.restriccions ?? []).filter(
        (r) => !["R1-TORN", "R2-FINESTRA", "R3-AULA"].includes(r.regla),
      );
      expect(ausents).toHaveLength(17);
      for (const regla of ausents) {
        expect(regla).toMatchObject({ total: 0, compten: 0, declarades: 0, heretades: 0, estat: "OK" });
      }
    });

    it("noAvaluables sale ordenado por regla", async () => {
      const { body } = await informe(idComplet);
      expect(body.informe?.noAvaluables).toEqual([
        { regla: "R0-FORMAT", sessions: 1 },
        { regla: "R1-TORN", sessions: 3 },
        { regla: "R4-PLAB", sessions: 2 },
      ]);
    });

    it("objectius sale en camelCase con los valores *VsReferencia", async () => {
      const { body } = await informe(idComplet);
      expect(body.informe?.objectius).toEqual({
        horesMortesMin: 120,
        desplacamentsAula: 7,
        desplacamentsEdifici: 3,
        canvisFranja: 4,
        canvisAula: 5,
        r6AulesTeExtraPerGrup: 2,
        r6CanvisTePaulForaPassadis: 6,
        sessionsAvaluades: 28,
        canvisFranjaVsReferencia: 9,
        canvisAulaVsReferencia: 0,
      });
    });

    it("copia relaxacionsDeclarades e incomplimentsDeclarats", async () => {
      const { body } = await informe(idComplet);
      expect(body.informe?.relaxacionsDeclarades).toBe(3);
      expect(body.informe?.incomplimentsDeclarats).toBe(1);
    });

    it("el informe solo tiene las claves del contrato", async () => {
      const { body } = await informe(idComplet);
      expect(Object.keys(body.informe ?? {}).sort()).toEqual(
        ["context", "incomplimentsDeclarats", "noAvaluables", "objectius", "relaxacionsDeclarades", "restriccions"].sort(),
      );
    });

    it("context solo expone semestre y nomesAules; no filtra ruta, hashes ni claves extra", async () => {
      const { body, text } = await informe(idComplet);
      expect(body.informe?.context).toEqual({ semestre: 1, nomesAules: true });
      expect(text).not.toContain("secret");
      expect(text).not.toContain("sha256");
      expect(text).not.toContain(CONTINGUT_PRIVAT);
      expect(text).not.toContain("escenari");
    });

    it("objectius sin *_vs_referencia devuelve null en esas dos claves", async () => {
      const { body } = await informe(idDesconeguda);
      expect(body.informe?.objectius.canvisFranjaVsReferencia).toBeNull();
      expect(body.informe?.objectius.canvisAulaVsReferencia).toBeNull();
      expect(body.informe?.objectius.horesMortesMin).toBe(0);
    });

    it("context con semestre null y nomes_aules false", async () => {
      const { body } = await informe(idDesconeguda);
      expect(body.informe?.context).toEqual({ semestre: null, nomesAules: false });
      expect(body.informe?.noAvaluables).toEqual([]);
    });
  });

  describe("reglas desconocidas", () => {
    it("se anaden al final en orden alfabetico tras las 20 conocidas", async () => {
      const { status, body } = await informe(idDesconeguda);
      expect(status).toBe(200);
      expect(body.veredicte).toBe("NO VALIDA");
      const noms = body.informe?.restriccions.map((r) => r.regla);
      expect(noms).toEqual([...REGLES, "R9-ALFA", "R9-NOVA"]);
    });

    it("calcula el estat de las desconocidas igual que el de las conocidas", async () => {
      const { body } = await informe(idDesconeguda);
      const finals = body.informe?.restriccions.slice(-2);
      expect(finals).toEqual([
        { regla: "R9-ALFA", total: 1, compten: 0, declarades: 1, heretades: 0, estat: "REL" },
        { regla: "R9-NOVA", total: 2, compten: 1, declarades: 0, heretades: 0, estat: "KO" },
      ]);
    });
  });

  describe("informe que no cumple el esquema", () => {
    it("responde 500 internal_error con requestId y sin filtrar el contenido", async () => {
      const res = await request(app).get(`/versions/${String(idInvalid)}/informe`);
      const body = res.body as { error: string; requestId?: string };
      expect(res.status).toBe(500);
      expect(body.error).toBe("internal_error");
      expect(typeof body.requestId).toBe("string");
      expect(Object.keys(body).sort()).toEqual(["error", "requestId"]);
      expect(res.text).not.toContain(CONTINGUT_PRIVAT);
      expect(res.text).not.toContain("restriccions");
    });
  });

  describe("entrada invalida", () => {
    it("version inexistente responde 404 not_found", async () => {
      const res = await request(app).get("/versions/999/informe");
      expect(res.status).toBe(404);
      expect(res.body).toEqual({ error: "not_found" });
    });

    it.each(["x", "0", "-1", "1.5", SENTINELLA])("id=%s responde 400 sin eco del valor", async (id) => {
      const res = await request(app).get(`/versions/${id}/informe`);
      expect(res.status).toBe(400);
      expect((res.body as { error: string }).error).toBe("invalid_request");
      expect(JSON.stringify(res.body)).not.toContain(SENTINELLA);
    });

    it("un id con SQL se rechaza con 400 y nunca 500", async () => {
      const res = await request(app).get(`/versions/${encodeURIComponent("1 OR 1=1")}/informe`);
      expect(res.status).toBe(400);
    });
  });
});
