import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import type { Database } from "better-sqlite3";
import { inject } from "vitest";
import { loadConfig } from "../src/config.js";
import { openDatabase } from "../src/db/connection.js";
import type { AppDeps } from "../src/http/app.js";
import { createLogger } from "../src/http/logger.js";

// Dependencias con la BD de fixtures abierta en solo lectura.
export function testDeps(): AppDeps {
  const dbPath = inject("dbPath");
  return {
    db: openDatabase(dbPath, { readonly: true }),
    config: loadConfig({ HORARIS_DB: dbPath, LOG_LEVEL: "silent" }),
    logger: createLogger("silent"),
  };
}

// Copia de la BD de fixtures en lectura/escritura; dispose() cierra la BD y borra el directorio temporal.
export function openWritableCopy(): { db: Database; path: string; dispose: () => void } {
  const dir = mkdtempSync(path.join(tmpdir(), "horaris-copy-"));
  const copyPath = path.join(dir, "copy.db");
  copyFileSync(inject("dbPath"), copyPath);
  const db = openDatabase(copyPath);
  return {
    db,
    path: copyPath,
    dispose: () => {
      db.close();
      rmSync(dir, { recursive: true, force: true });
    },
  };
}
