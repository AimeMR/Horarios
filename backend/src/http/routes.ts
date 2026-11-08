import type { Router } from "express";
import { aulesRouter } from "../features/aules/aules.controller.js";
import { healthRouter } from "../features/health/health.controller.js";
import { informeRouter } from "../features/informe/informe.controller.js";
import { ocupacioRouter } from "../features/ocupacio/ocupacio.controller.js";
import { parrillaRouter } from "../features/parrilla/parrilla.controller.js";
import { versionsRouter } from "../features/versions/versions.controller.js";
import type { AppDeps } from "./app.js";

export function registerRoutes(router: Router, deps: AppDeps): void {
  router.use("/health", healthRouter());
  router.use("/aules", aulesRouter(deps));
  router.use(
    "/versions",
    versionsRouter(deps),
    informeRouter(deps),
    parrillaRouter(deps),
    ocupacioRouter(deps),
  );
}
