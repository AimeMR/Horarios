import type { z } from "zod";
import { ValidationError } from "../domain/errors.js";

function describeRule(issue: z.core.$ZodIssue): string {
  switch (issue.code) {
    case "invalid_type":
      return `debe ser de tipo ${issue.expected}`;
    case "invalid_value":
      return "valor no permitido";
    case "too_small":
      return `debe ser >= ${String(issue.minimum)}`;
    case "too_big":
      return `debe ser <= ${String(issue.maximum)}`;
    case "custom":
      return issue.message;
    case "invalid_format":
      return "formato no válido";
    case "not_multiple_of":
      return "múltiplo no válido";
    default:
      return "valor no válido";
  }
}

function parseWith<T>(schema: z.ZodType<T>, input: unknown): T {
  const result = schema.safeParse(input);
  if (result.success) return result.data;
  throw new ValidationError(
    result.error.issues.map((issue) => ({
      path: issue.path.map(String).join("."),
      message: describeRule(issue),
    })),
  );
}

export function parseQuery<T>(schema: z.ZodType<T>, query: unknown): T {
  return parseWith(schema, query);
}

export function parseParams<T>(schema: z.ZodType<T>, params: unknown): T {
  return parseWith(schema, params);
}
