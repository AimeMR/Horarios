export class NotFoundError extends Error {
  override name = "NotFoundError";
}

export class ValidationError extends Error {
  override name = "ValidationError";

  constructor(readonly issues: ReadonlyArray<{ path: string; message: string }>) {
    super("Petición no válida");
  }
}

export class NotImplementedError extends Error {
  override name = "NotImplementedError";
}
