import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runScript } from "../shared/hunt-bridge";

export default defineAction({
  description:
    "Simule les relances J+3 à J+10 : indique celles qui seraient préparées et vérifie dans Gmail si une réponse est arrivée. Aucune écriture, aucun brouillon, aucun envoi (le mode --apply du script n'est volontairement pas exposé).",
  mcpTool: true,
  schema: z.object({}),
  http: { method: "POST" },
  run: async () => {
    const { stdout, stderr, exitCode } = await runScript("run_followups.py", [], { timeout: 180000 });

    return {
      success: exitCode === 0,
      report: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
