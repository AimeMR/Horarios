import express from "express";
import type { AppDeps } from "../../http/app.js";
import { idVersioParamsSchema } from "../../http/params.js";
import { parseParams, parseQuery } from "../../http/validate.js";
import { toAssignacioDto, toVersioDto, versionsQuerySchema } from "./versions.dto.js";
import { createVersionsRepository } from "./versions.repository.js";
import { createVersionsService } from "./versions.service.js";

export function versionsRouter(deps: AppDeps): express.Router {
  const service = createVersionsService(createVersionsRepository(deps.db));
  const router = express.Router();

  router.get("/", (req, res) => {
    const { limit, offset } = parseQuery(versionsQuerySchema, req.query);
    const page = service.listVersions(limit, offset);
    res.json({ ...page, items: page.items.map(toVersioDto) });
  });

  router.get("/:id/assignacions", (req, res) => {
    const { id } = parseParams(idVersioParamsSchema, req.params);
    const { limit, offset } = parseQuery(versionsQuerySchema, req.query);
    const page = service.listAssignacions(id, limit, offset);
    res.json({ ...page, items: page.items.map(toAssignacioDto) });
  });

  return router;
}
