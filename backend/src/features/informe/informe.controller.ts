import express from "express";
import type { AppDeps } from "../../http/app.js";
import { idVersioParamsSchema } from "../../http/params.js";
import { parseParams } from "../../http/validate.js";
import { toInformeVersioDto } from "./informe.dto.js";
import { getInforme } from "./informe.service.js";

export function informeRouter(deps: AppDeps): express.Router {
  const router = express.Router();
  router.get("/:id/informe", (req, res) => {
    const { id } = parseParams(idVersioParamsSchema, req.params);
    res.status(200).json(toInformeVersioDto(getInforme(deps.db, id)));
  });
  return router;
}
