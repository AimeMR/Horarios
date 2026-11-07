import { NotImplementedError } from "../../domain/errors.js";

export interface VerificadorService {
  verificar(versio: string): Promise<never>;
}

export function createVerificadorService(): VerificadorService {
  return {
    verificar: () => Promise.reject(new NotImplementedError("verificador not implemented")),
  };
}
