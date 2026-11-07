import { loadConfig } from "./config.js";
import { openDatabase } from "./db/connection.js";
import { createApp } from "./http/app.js";
import { createLogger } from "./http/logger.js";

const config = loadConfig();
const logger = createLogger(config.logLevel);
const db = openDatabase(config.dbPath);
const app = createApp({ db, config, logger });

const server = app.listen(config.port, config.host, () => {
  logger.info(`escuchando en ${config.host}:${config.port}`);
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
