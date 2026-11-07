import express from "express";
import type { AppDeps } from "../../http/app.js";
import { idVersioParamsSchema } from "../../http/params.js";
import { parseParams, parseQuery } from "../../http/validate.js";
import { ocupacioQuerySchema, toOcupacioDto } from "./ocupacio.dto.js";
import { OcupacioRepository } from "./ocupacio.repository.js";
import { OcupacioService } from "./ocupacio.service.js";

export function ocupacioRouter(deps: AppDeps): express.Router {
  const router = express.Router();
  const service = new OcupacioService(new OcupacioRepository(deps.db));

  router.get("/:id/ocupacio", (req, res) => {
    const { id } = parseParams(idVersioParamsSchema, req.params);
    const query = parseQuery(ocupacioQuerySchema, req.query);
    res.json(toOcupacioDto(service.calcula(id, { setmana: query.setmana, tipus: query.tipus })));
  });

  return router;
}
