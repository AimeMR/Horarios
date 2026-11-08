import { describe, expect, it } from "vitest";
import { NotImplementedError } from "../../domain/errors.js";
import { createSolverService } from "./solver.service.js";

describe("createSolverService", () => {
  it("executar rechaza con NotImplementedError", async () => {
    await expect(createSolverService().executar("x")).rejects.toBeInstanceOf(NotImplementedError);
  });
});
