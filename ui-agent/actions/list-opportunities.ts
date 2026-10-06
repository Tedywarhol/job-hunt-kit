import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { readWorkspaceJson } from "../shared/hunt-bridge";
import type { OpportunityItem } from "../shared/dashboard-types";

export default defineAction({
  description: "Lister les opportunités d'emploi/alternance détectées et scorées dans le radar.",
  mcpTool: true,
  schema: z.object({
    source: z.enum(["all", "ats", "pass"]).default("all").describe("Filtrer par source : all, ats, ou pass"),
    minScore: z.number().default(0).describe("Score de pertinence minimal (ex: 50)"),
    limit: z.number().default(20).describe("Nombre maximal d'opportunités à renvoyer"),
  }),
  http: { method: "GET" },
  run: async ({ source, minScore, limit }) => {
    const pendingNotion = readWorkspaceJson<OpportunityItem[] | { offres: OpportunityItem[] }>("state/pending-notion-upsert.json");
    const passScored = readWorkspaceJson<OpportunityItem[] | { offres: OpportunityItem[] }>("state/pass_alternance_scored.json");

    const extractList = (raw: OpportunityItem[] | { offres: OpportunityItem[] } | null, defaultSource: string): OpportunityItem[] => {
      if (!raw) return [];
      const items = Array.isArray(raw) ? raw : Array.isArray(raw.offres) ? raw.offres : [];
      return items.map((item) => ({ ...item, source: item.source ?? defaultSource }));
    };

    let allOffers: OpportunityItem[] = [];
    if (source === "all" || source === "ats") {
      allOffers.push(...extractList(pendingNotion, "ATS direct"));
    }
    if (source === "all" || source === "pass") {
      allOffers.push(...extractList(passScored, "PASS"));
    }

    const seen = new Set<string>();
    const filtered: OpportunityItem[] = [];

    for (const item of allOffers) {
      const score = item.score_pertinence ?? item.score ?? 0;
      if (score < minScore) continue;

      const key = item.lien || `${item.entreprise}-${item.intitule || item.poste}`;
      if (key && !seen.has(key)) {
        seen.add(key);
        filtered.push(item);
      }
    }

    filtered.sort((a, b) => (b.score_pertinence ?? b.score ?? 0) - (a.score_pertinence ?? a.score ?? 0));

    return {
      totalFound: filtered.length,
      limit,
      opportunities: filtered.slice(0, limit).map((o) => ({
        entreprise: o.entreprise,
        poste: o.intitule || o.poste,
        score: o.score_pertinence ?? o.score ?? 0,
        ageJours: o.age_jours ?? 0,
        datePublication: o.date_publication,
        lieu: o.lieu,
        lien: o.lien,
        source: o.source,
      })),
    };
  },
});
