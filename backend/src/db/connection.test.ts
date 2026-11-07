import { mkdtempSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import Database from "better-sqlite3";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openDatabase } from "./connection.js";

let dir = "";
let dbFile = "";

beforeAll(() => {
  dir = mkdtempSync(path.join(tmpdir(), "horaris-conn-"));
  dbFile = path.join(dir, "test.db");
  const seed = new Database(dbFile);
  seed.exec(`
    CREATE TABLE pare (id INTEGER PRIMARY KEY);
    CREATE TABLE fill (id INTEGER PRIMARY KEY, pare_id INTEGER NOT NULL REFERENCES pare(id));
    INSERT INTO pare (id) VALUES (1);
  `);
  seed.close();
});

afterAll(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("openDatabase", () => {
  it("abre un fichero existente con foreign_keys activado y busy_timeout de 5000", () => {
    const db = openDatabase(dbFile);
    try {
      expect(db.pragma("foreign_keys", { simple: true })).toBe(1);
      expect(db.pragma("busy_timeout", { simple: true })).toBe(5000);
      expect(db.prepare("SELECT COUNT(*) AS n FROM pare").get()).toEqual({ n: 1 });
    } finally {
      db.close();
    }
  });

  it("permite escribir por defecto", () => {
    const db = openDatabase(dbFile);
    try {
      db.prepare("INSERT INTO fill (id, pare_id) VALUES (1, 1)").run();
      db.prepare("DELETE FROM fill WHERE id = 1").run();
    } finally {
      db.close();
    }
  });

  it("rechaza una fila que viola una clave foránea", () => {
    const db = openDatabase(dbFile);
    try {
      expect(() => db.prepare("INSERT INTO fill (id, pare_id) VALUES (2, 999)").run()).toThrow(/FOREIGN KEY/i);
    } finally {
      db.close();
    }
  });

  it("lanza si el fichero no existe y no lo crea", () => {
    const missing = path.join(dir, "no-existe.db");
    expect(() => openDatabase(missing)).toThrow();
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- ruta temporal creada por el propio test
    expect(existsSync(missing)).toBe(false);
  });

  it("con readonly impide escribir pero permite leer", () => {
    const db = openDatabase(dbFile, { readonly: true });
    try {
      expect(db.readonly).toBe(true);
      expect(db.prepare("SELECT COUNT(*) AS n FROM pare").get()).toEqual({ n: 1 });
      expect(() => db.prepare("INSERT INTO pare (id) VALUES (50)").run()).toThrow(/readonly/i);
    } finally {
      db.close();
    }
  });

  it("con readonly sobre un fichero inexistente también lanza", () => {
    const missing = path.join(dir, "tampoco.db");
    expect(() => openDatabase(missing, { readonly: true })).toThrow();
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- ruta temporal creada por el propio test
    expect(existsSync(missing)).toBe(false);
  });
});
