import { execFile, type ExecFileException } from "node:child_process";

export interface RunOptions {
  readonly cwd?: string;
  readonly timeoutMs: number;
  readonly maxBufferBytes?: number;
  readonly env?: NodeJS.ProcessEnv;
}

export interface RunResult {
  readonly exitCode: number;
  readonly stdout: string;
  readonly stderr: string;
}

export class ProcessTimeoutError extends Error {
  constructor(options?: ErrorOptions) {
    super("process timed out", options);
    this.name = "ProcessTimeoutError";
  }
}

const DEFAULT_MAX_BUFFER = 1024 * 1024;

type ExecFailure = ExecFileException;

function isTimeout(error: ExecFailure): boolean {
  return error.code === "ETIMEDOUT" || (error.killed === true && Boolean(error.signal));
}

function failureFrom(error: ExecFailure): Error {
  if (isTimeout(error)) {
    return new ProcessTimeoutError({ cause: error });
  }
  if (error.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER") {
    return new Error("process output exceeded the buffer limit", { cause: error });
  }
  return new Error("process failed to run", { cause: error });
}

export function runProcess(
  file: string,
  args: readonly string[],
  options: RunOptions,
): Promise<RunResult> {
  return new Promise<RunResult>((resolve, reject) => {
    // Sin shell: execFile con argumentos en array; el fichero lo fija nuestro código.
    execFile(
      file,
      [...args],
      {
        cwd: options.cwd,
        env: options.env,
        timeout: options.timeoutMs,
        killSignal: "SIGKILL",
        maxBuffer: options.maxBufferBytes ?? DEFAULT_MAX_BUFFER,
        windowsHide: true,
        encoding: "utf8",
      },
      (error, stdout, stderr) => {
        if (error === null) {
          resolve({ exitCode: 0, stdout, stderr });
          return;
        }
        const failure: ExecFailure = error;
        if (typeof failure.code === "number" && !isTimeout(failure)) {
          resolve({ exitCode: failure.code, stdout, stderr });
          return;
        }
        reject(failureFrom(failure));
      },
    );
  });
}
