import Database from "better-sqlite3";
import type { Database as SqliteDatabase } from "better-sqlite3";

export interface OpenDatabaseOptions {
  readonly readonly?: boolean;
}

// El backend nunca crea la BD ni ejecuta DDL: la crean las migraciones del extractor.
export function openDatabase(path: string, options: OpenDatabaseOptions = {}): SqliteDatabase {
  const db = new Database(path, { fileMustExist: true, readonly: options.readonly === true });
  try {
    db.pragma("foreign_keys = ON");
    if (db.pragma("foreign_keys", { simple: true }) !== 1) {
      throw new Error("No se pudo activar foreign_keys en SQLite");
    }
    db.pragma("busy_timeout = 5000");
  } catch (error) {
    db.close();
    throw error;
  }
  return db;
}
