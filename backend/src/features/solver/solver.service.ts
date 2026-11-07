import { NotImplementedError } from "../../domain/errors.js";

export interface SolverService {
  executar(versioOrigen: string): Promise<never>;
}

export function createSolverService(): SolverService {
  return {
    executar: () => Promise.reject(new NotImplementedError("solver not implemented")),
  };
}
