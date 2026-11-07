import express from "express";
import type { AppDeps } from "../../http/app.js";
import { idVersioParamsSchema } from "../../http/params.js";
import { parseParams, parseQuery } from "../../http/validate.js";
import { parrillaQuerySchema, toParrillaDto } from "./parrilla.dto.js";
import { consultarParrilla } from "./parrilla.service.js";

export function parrillaRouter(deps: AppDeps): express.Router {
  const router = express.Router();
  router.get("/:id/parrilla", (req, res) => {
    const { id } = parseParams(idVersioParamsSchema, req.params);
    const consulta = parseQuery(parrillaQuerySchema, req.query);
    res.json(toParrillaDto(consultarParrilla(deps.db, id, consulta)));
  });
  return router;
}
