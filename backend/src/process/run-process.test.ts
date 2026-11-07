import { readFileSync, realpathSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ProcessTimeoutError, runProcess } from "./run-process.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const procDir = path.resolve(here, "../../test/fixtures/proc");

function script(name: string): string {
  return path.join(procDir, name);
}

async function rejectionOf(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  return undefined;
}

describe("runProcess", () => {
  it("pasa los argumentos intactos, sin shell", async () => {
    const args = [
      "a b",
      "x;y",
      "a&&b",
      "a|b",
      "$(whoami)",
      "`id`",
      'say "hi"',
      "it's",
      "%PATH%",
      "",
    ];
    const result = await runProcess(process.execPath, [script("echo-args.mjs"), ...args], {
      timeoutMs: 10000,
    });
    expect(result.exitCode).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual(args);
  });

  it("resuelve con exitCode 0 y captura stdout y stderr", async () => {
    const result = await runProcess(process.execPath, [script("exit-code.mjs"), "0"], {
      timeoutMs: 10000,
    });
    expect(result).toEqual({ exitCode: 0, stdout: "out", stderr: "err" });
  });

  it("resuelve (no rechaza) con un código de salida distinto de 0", async () => {
    const result = await runProcess(process.execPath, [script("exit-code.mjs"), "3"], {
      timeoutMs: 10000,
    });
    expect(result.exitCode).toBe(3);
    expect(result.stdout).toBe("out");
    expect(result.stderr).toBe("err");
  });

  it("rechaza con ProcessTimeoutError cerca del timeout, no del sueño completo", async () => {
    const started = Date.now();
    const error = await rejectionOf(
      runProcess(process.execPath, [script("sleep.mjs"), "20000"], { timeoutMs: 500 }),
    );
    const elapsed = Date.now() - started;
    expect(error).toBeInstanceOf(ProcessTimeoutError);
    expect(elapsed).toBeLessThan(10000);
  });

  it("rechaza con un Error genérico si la salida supera maxBufferBytes", async () => {
    const error = await rejectionOf(
      runProcess(process.execPath, [script("flood.mjs"), "20000"], {
        timeoutMs: 10000,
        maxBufferBytes: 1000,
      }),
    );
    expect(error).toBeInstanceOf(Error);
    expect(error).not.toBeInstanceOf(ProcessTimeoutError);
    expect((error as Error).message).not.toContain("SECRETFLOOD");
  });

  it("acepta salida menor que maxBufferBytes", async () => {
    const result = await runProcess(process.execPath, [script("flood.mjs"), "500"], {
      timeoutMs: 10000,
      maxBufferBytes: 1000,
    });
    expect(result.stdout).toHaveLength(500);
  });

  it("rechaza con un Error genérico si el ejecutable no existe", async () => {
    const error = await rejectionOf(
      runProcess(path.join(procDir, "no-existe-xyz"), [], { timeoutMs: 5000 }),
    );
    expect(error).toBeInstanceOf(Error);
    expect(error).not.toBeInstanceOf(ProcessTimeoutError);
  });

  it("respeta cwd y env", async () => {
    const dir = realpathSync(os.tmpdir());
    const result = await runProcess(process.execPath, [script("print-cwd-env.mjs")], {
      timeoutMs: 10000,
      cwd: dir,
      env: { ...process.env, PROC_TEST_VAR: "valor-de-prueba" },
    });
    const parsed = JSON.parse(result.stdout) as { cwd: string; value: string | null };
    expect(realpathSync(parsed.cwd)).toBe(dir);
    expect(parsed.value).toBe("valor-de-prueba");
  });

  // Comprobación de contrato (estática): la implementación nunca usa shell ni exec.
  it("el código fuente no usa shell: true ni exec(", () => {
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- ruta fija calculada en este fichero
    const source = readFileSync(path.join(here, "run-process.ts"), "utf8");
    expect(source).not.toMatch(/shell\s*:\s*true/);
    expect(source.replace(/execFile/g, "")).not.toMatch(/\bexec\s*\(/);
  });
});
