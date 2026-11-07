import { z } from "zod";
import { dillunsDeSetmana } from "../domain/setmana.js";

export const idVersioParamsSchema = z.object({
  id: z.coerce.number().int().min(1),
});

export const setmanaSchema = z.string().regex(/^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/);

export const setmanaExistentSchema = setmanaSchema.superRefine((setmana, ctx) => {
  try {
    dillunsDeSetmana(setmana);
  } catch (error) {
    if (!(error instanceof RangeError)) {
      throw error;
    }
    ctx.addIssue({ code: "custom", message: "setmana inexistent" });
  }
});
