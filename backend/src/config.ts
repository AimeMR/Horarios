import { z } from "zod";

export const LOG_LEVELS = ["fatal", "error", "warn", "info", "debug", "trace", "silent"] as const;

export interface Config {
  readonly dbPath: string;
  readonly host: string;
  readonly port: number;
  readonly corsOrigin: string;
  readonly logLevel: (typeof LOG_LEVELS)[number];
}

const envSchema = z.object({
  HORARIS_DB: z.string().min(1),
  HOST: z.string().min(1).default("127.0.0.1"),
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  CORS_ORIGIN: z.string().min(1).default("http://localhost:5173"),
  LOG_LEVEL: z.enum(LOG_LEVELS).default("info"),
});

export function loadConfig(source: NodeJS.ProcessEnv = process.env): Config {
  const parsed = envSchema.safeParse(source);
  if (!parsed.success) {
    const names = [...new Set(parsed.error.issues.map((issue) => String(issue.path[0])))];
    throw new Error(`Configuración inválida: revisa las variables ${names.join(", ")}`);
  }
  const values = parsed.data;
  return {
    dbPath: values.HORARIS_DB,
    host: values.HOST,
    port: values.PORT,
    corsOrigin: values.CORS_ORIGIN,
    logLevel: values.LOG_LEVEL,
  };
}
