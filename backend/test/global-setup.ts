import { execFile } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import type { TestProject } from "vitest/node";

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// Crea la BD de fixtures con las migraciones del extractor (datos falsos).
export default async function setup(project: TestProject): Promise<() => Promise<void>> {
  const dir = await mkdtemp(path.join(tmpdir(), "horaris-test-"));
  const dbPath = path.join(dir, "test.db");
  try {
    await execFileAsync(
      "uv",
      ["run", "extractor", "--db", dbPath, "setup", "--paquet", "tests/fixtures/paquet_fals"],
      { cwd: repoRoot, timeout: 120000, windowsHide: true },
    );
  } catch (error) {
    await rm(dir, { recursive: true, force: true });
    const stderr = (error as { stderr?: unknown }).stderr;
    const detail = typeof stderr === "string" && stderr !== "" ? stderr : String(error);
    throw new Error(`No se pudo crear la BD de fixtures: ${detail}`, { cause: error });
  }
  project.provide("dbPath", dbPath);
  return async () => {
    await rm(dir, { recursive: true, force: true });
  };
}
