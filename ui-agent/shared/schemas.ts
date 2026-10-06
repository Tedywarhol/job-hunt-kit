import { z } from "zod";

/** Folder name under outputs/: lowercase, digits, dashes. Shared by the actions and the screen form. */
export const SLUG_PATTERN = /^[a-z0-9][a-z0-9_-]{0,119}$/;

export const slugSchema = z
  .string()
  .trim()
  .regex(SLUG_PATTERN, "Slug en minuscules, chiffres et tirets (ex: acme-data-engineer)");

/** Addresses go to a script as arguments: a value starting with "-" could be read as an option. */
export const emailListSchema = z
  .array(z.string().regex(/^[^\s@-][^\s@]*@[^\s@]+$/, "Adresse email attendue"))
  .min(1)
  .max(20);
