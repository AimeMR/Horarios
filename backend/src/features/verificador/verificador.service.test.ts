import { describe, expect, it } from "vitest";
import { NotImplementedError } from "../../domain/errors.js";
import { createVerificadorService } from "./verificador.service.js";

describe("createVerificadorService", () => {
  it("verificar rechaza con NotImplementedError", async () => {
    await expect(createVerificadorService().verificar("x")).rejects.toBeInstanceOf(
      NotImplementedError,
    );
  });
});
