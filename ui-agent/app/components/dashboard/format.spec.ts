import { describe, expect, it } from "vitest";
import { barWidth, groupRelances, orderRows, relanceLabel, relanceTone, slugify, FUNNEL_ORDER } from "./format";

describe("dashboard format helpers", () => {
  it("labels follow-ups as late, today or soon", () => {
    expect(relanceLabel(-11)).toBe("En retard de 11 j");
    expect(relanceLabel(0)).toBe("Aujourd'hui");
    expect(relanceLabel(2)).toBe("Dans 2 j");
    expect([relanceTone(-1), relanceTone(0), relanceTone(3)]).toEqual(["late", "today", "soon"]);
  });

  it("groups follow-ups by urgency", () => {
    const make = (jours: number) => ({ entreprise: "Acme", poste: "Data", etape_suivante: "J+3", echeance: "2026-10-06", jours });
    const grouped = groupRelances([make(-5), make(0), make(1), make(-1)]);
    expect([grouped.late.length, grouped.today.length, grouped.soon.length]).toEqual([2, 1, 1]);
  });

  it("orders known statuses first, then the others by count, and hides empty ones", () => {
    const rows = orderRows({ Refusé: 4, Postulé: 10, "Autre statut": 3, Entretien: 0, "À traiter": 1, Zéro: 0 }, FUNNEL_ORDER);
    expect(rows.map((r) => r.label)).toEqual(["À traiter", "Postulé", "Refusé", "Autre statut"]);
  });

  it("keeps a visible sliver for small values and no bar for zero", () => {
    expect(barWidth(100, 100)).toBe("100%");
    expect(barWidth(1, 1000)).toBe("4%");
    expect(barWidth(0, 10)).toBe("0%");
    expect(barWidth(5, 0)).toBe("0%");
  });

  it("builds a slug without accents or symbols", () => {
    expect(slugify("Société Générale : Data Analyst (H/F)")).toBe("societe-generale-data-analyst-h-f");
    expect(slugify("  --Acme--  ")).toBe("acme");
  });
});
