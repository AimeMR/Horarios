import { z } from "zod";

export const idVersioParamsSchema = z.object({
  id: z.coerce.number().int().min(1),
});

export const setmanaSchema = z.string().regex(/^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/);
