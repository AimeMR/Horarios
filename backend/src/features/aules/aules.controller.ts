import express from "express";
import type { AppDeps } from "../../http/app.js";
import type { Page } from "../../http/pagination.js";
import { parseQuery } from "../../http/validate.js";
import { aulesQuerySchema, toAulaDto, type AulaDto } from "./aules.dto.js";
import { createAulesRepository } from "./aules.repository.js";
import { createAulesService } from "./aules.service.js";

export function aulesRouter(deps: AppDeps): express.Router {
  const service = createAulesService(createAulesRepository(deps.db));
  const router = express.Router();

  router.get("/", (req, res) => {
    const query = parseQuery(aulesQuerySchema, req.query);
    const page = service.list({
      tipus: query.tipus,
      capacitatMin: query.capacitat_min,
      limit: query.limit,
      offset: query.offset,
    });
    const body: Page<AulaDto> = { ...page, items: page.items.map(toAulaDto) };
    res.json(body);
  });

  return router;
}
