import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import type { DashboardData } from "../shared/dashboard-types";
import { runHuntCommand, runScript } from "../shared/hunt-bridge";

export default defineAction({
  description:
    "Tableau de bord Job-Hunt : relances dues, statuts réels des candidatures, fraîcheur et meilleures offres, dossiers récents et réseau de contacts par niveau de confiance. Lecture seule. Mettre notion=true pour inclure le statut réel dans Notion (plus lent).",
  mcpTool: true,
  schema: z.object({
    format: z
      .enum(["json", "text"])
      .default("json")
      .describe("json : données structurées. text : le tableau de bord console de `hunt.py stats`."),
    notion: z
      .boolean()
      .default(false)
      .describe("Interroger Notion pour le statut réel des candidatures (quelques secondes de plus)."),
  }),
  http: { method: "GET" },
  run: async ({ format, notion }) => {
    if (format === "text") {
      const { stdout } = await runHuntCommand(["stats"], { timeout: 90000 });
      return { output: stdout };
    }

    // HUNT_UI_DEMO=1 : données fictives, pour essayer l'écran ou le photographier sans exposer de vrais contacts.
    const args = process.env.HUNT_UI_DEMO === "1" ? ["--demo"] : notion ? [] : ["--sans-notion"];
    const { stdout, stderr, exitCode } = await runScript("ui_data.py", args, { timeout: 90000 });
    if (exitCode !== 0) {
      throw new Error(`ui_data.py a échoué (code ${exitCode}) : ${stderr.trim() || "aucun détail"}`);
    }
    try {
      return JSON.parse(stdout) as DashboardData;
    } catch {
      throw new Error("ui_data.py n'a pas renvoyé du JSON valide.");
    }
  },
});
