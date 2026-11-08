import { isLoopbackHost, loadConfig } from "./config.js";
import { openDatabase } from "./db/connection.js";
import { createApp } from "./http/app.js";
import { createLogger } from "./http/logger.js";

const config = loadConfig();
const logger = createLogger(config.logLevel);
const db = openDatabase(config.dbPath, { readonly: true });
const app = createApp({ db, config, logger });

const server = app.listen(config.port, config.host, (err?: Error) => {
  if (err !== undefined) {
    logger.fatal({ code: (err as NodeJS.ErrnoException).code }, "no se pudo abrir el puerto");
    db.close();
    process.exitCode = 1;
    return;
  }
  logger.info(`escuchando en ${config.host}:${config.port}`);
  if (!isLoopbackHost(config.host)) {
    logger.warn("la API no tiene autenticación y está expuesta fuera de esta máquina");
  }
});

function shutdown(signal: string): void {
  logger.info(`señal ${signal} recibida, cerrando`);
  server.close(() => {
    db.close();
    process.exit(0);
  });
}

process.on("SIGINT", () => {
  shutdown("SIGINT");
});
process.on("SIGTERM", () => {
  shutdown("SIGTERM");
});
