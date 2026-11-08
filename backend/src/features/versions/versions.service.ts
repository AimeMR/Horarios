import type { Assignacio } from "../../domain/assignacio.js";
import { NotFoundError } from "../../domain/errors.js";
import type { Versio } from "../../domain/versio.js";
import type { Page } from "../../http/pagination.js";
import type { VersionsRepository } from "./versions.repository.js";

export interface VersionsService {
  listVersions(limit: number, offset: number): Page<Versio>;
  listAssignacions(id: number, limit: number, offset: number): Page<Assignacio>;
}

export function createVersionsService(repo: VersionsRepository): VersionsService {
  return {
    listVersions(limit, offset) {
      return { items: repo.listVersions(limit, offset), total: repo.countVersions(), limit, offset };
    },
    listAssignacions(id, limit, offset) {
      if (!repo.versioExists(id)) throw new NotFoundError("versio");
      return { items: repo.listAssignacions(id, limit, offset), total: repo.countAssignacions(id), limit, offset };
    },
  };
}
