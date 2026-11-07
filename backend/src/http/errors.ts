import { randomUUID } from "node:crypto";
import type { ErrorRequestHandler, RequestHandler, Response } from "express";
import { NotFoundError, NotImplementedError, ValidationError } from "../domain/errors.js";
import type { Logger } from "./logger.js";

const BODY_PARSER_TYPES = new Set(["entity.parse.failed", "entity.too.large"]);

export function notFoundHandler(): RequestHandler {
  return (_req, res) => {
    res.status(404).json({ error: "not_found" });
  };
}

function isBodyParserError(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const { type, status } = err as { type?: unknown; status?: unknown };
  if (typeof type === "string" && BODY_PARSER_TYPES.has(type)) return true;
  return typeof type === "string" && (status === 400 || status === 413);
}

function isClientError(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const { status, statusCode } = err as { status?: unknown; statusCode?: unknown };
  return [status, statusCode].some((c) => typeof c === "number" && c >= 400 && c <= 499);
}

function requestIdOf(res: Response): string {
  const local: unknown = res.locals["requestId"];
  if (typeof local === "string" && local !== "") return local;
  const header = res.getHeader("x-request-id");
  if (typeof header === "string" && header !== "") return header;
  return randomUUID();
}

export function errorHandler(logger: Logger): ErrorRequestHandler {
  return (err: unknown, _req, res, next) => {
    if (res.headersSent) {
      next(err);
      return;
    }
    if (err instanceof NotFoundError) {
      res.status(404).json({ error: "not_found" });
    } else if (err instanceof ValidationError) {
      res.status(400).json({ error: "invalid_request", issues: err.issues });
    } else if (err instanceof NotImplementedError) {
      res.status(501).json({ error: "not_implemented" });
    } else if (isBodyParserError(err) || isClientError(err)) {
      // Sin mensaje del error: p. ej. el URIError de Express incluye el parámetro crudo.
      logger.warn({ requestId: requestIdOf(res) }, "petición rechazada");
      res.status(400).json({ error: "invalid_request" });
    } else {
      const requestId = requestIdOf(res);
      logger.error({ err, requestId }, "error no controlado");
      res.status(500).json({ error: "internal_error", requestId });
    }
  };
}
