import { describe, expect, it, vi } from "vitest";
import action from "./list-opportunities";
import * as bridge from "../shared/hunt-bridge";

describe("list-opportunities action", () => {
  it("filters and sorts opportunities by score and limit", async () => {
    vi.spyOn(bridge, "readWorkspaceJson").mockImplementation((relPath: string) => {
      if (relPath === "state/pending-notion-upsert.json") {
        return [
          { entreprise: "Company A", intitule: "Data Analyst", score_pertinence: 60, lien: "http://comp-a.com" },
          { entreprise: "Company B", intitule: "Data Scientist", score_pertinence: 95, lien: "http://comp-b.com" },
        ];
      }
      if (relPath === "state/pass_alternance_scored.json") {
        return [
          { entreprise: "Ministry", poste: "IA Lead", score: 80, lien: "http://pass.com/1" },
        ];
      }
      return null;
    });

    const res = await action.run({ source: "all", minScore: 70, limit: 10 });
    expect(res.totalFound).toBe(2);
    expect(res.opportunities[0].score).toBe(95);
    expect(res.opportunities[0].entreprise).toBe("Company B");
    expect(res.opportunities[1].score).toBe(80);

    vi.restoreAllMocks();
  });

  it("filters by source ats only", async () => {
    vi.spyOn(bridge, "readWorkspaceJson").mockImplementation((relPath: string) => {
      if (relPath === "state/pending-notion-upsert.json") {
        return [
          { entreprise: "Company A", intitule: "Data Analyst", score_pertinence: 60, lien: "http://comp-a.com" },
        ];
      }
      if (relPath === "state/pass_alternance_scored.json") {
        return [
          { entreprise: "Ministry", poste: "IA Lead", score: 80, lien: "http://pass.com/1" },
        ];
      }
      return null;
    });

    const res = await action.run({ source: "ats", minScore: 0, limit: 10 });
    expect(res.totalFound).toBe(1);
    expect(res.opportunities[0].entreprise).toBe("Company A");

    vi.restoreAllMocks();
  });
});
