import { randomUUID } from "node:crypto";
import cors from "cors";
import express, { type RequestHandler } from "express";
import helmet from "helmet";
import type { Database } from "better-sqlite3";
import type { Config } from "../config.js";
import { errorHandler, notFoundHandler } from "./errors.js";
import type { Logger } from "./logger.js";
import { registerRoutes } from "./routes.js";

export interface AppDeps {
  readonly db: Database;
  readonly config: Config;
  readonly logger: Logger;
}

const requestId: RequestHandler = (_req, res, next) => {
  const id = randomUUID();
  res.locals["requestId"] = id;
  res.setHeader("x-request-id", id);
  next();
};

export function createApp(deps: AppDeps): express.Express {
  const app = express();
  app.disable("x-powered-by");
  app.use(requestId);
  app.use(helmet());
  app.use(cors({ origin: [deps.config.corsOrigin] }));
  app.use(express.json({ limit: "100kb" }));
  const router = express.Router();
  registerRoutes(router, deps);
  app.use(router);
  app.use(notFoundHandler());
  app.use(errorHandler(deps.logger));
  return app;
}
