import { describe, expect, it } from "vitest";
import { emailListSchema, slugSchema } from "./schemas";

describe("shared schemas", () => {
  it.each(["acme-data-engineer", "a", "chu-paris-ml_2026"])("accepts the slug %j", (slug) => {
    expect(slugSchema.safeParse(slug).success).toBe(true);
  });

  it.each(["Acme / Data!", "../state", "acme data", "-acme", "", "a".repeat(121)])("rejects the slug %j", (slug) => {
    expect(slugSchema.safeParse(slug).success).toBe(false);
  });

  it("accepts addresses and rejects anything that could be read as an option or a path", () => {
    expect(emailListSchema.safeParse(["a@exemple.fr", "b.c@conseil-exemple.com"]).success).toBe(true);
    expect(emailListSchema.safeParse(["--refresh"]).success).toBe(false);
    expect(emailListSchema.safeParse(["-x@exemple.fr"]).success).toBe(false);
    expect(emailListSchema.safeParse(["a b@exemple.fr"]).success).toBe(false);
    expect(emailListSchema.safeParse([]).success).toBe(false);
  });
});
