import type { Aula } from "../../domain/aula.js";
import type { Page } from "../../http/pagination.js";
import type { AulaFilters, AulesRepository } from "./aules.repository.js";

export function createAulesService(repository: AulesRepository) {
  return {
    list(filters: AulaFilters): Page<Aula> {
      const { items, total } = repository.list(filters);
      return { items, total, limit: filters.limit, offset: filters.offset };
    },
  };
}
