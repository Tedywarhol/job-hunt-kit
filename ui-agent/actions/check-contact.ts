import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runScript } from "../shared/hunt-bridge";
import { emailListSchema } from "../shared/schemas";

export default defineAction({
  description:
    "Garde-fou à appeler AVANT de préparer un message : indique si une adresse, ou son entreprise, a déjà refusé (BLOQUÉ : même adresse, ATTENTION : même entreprise récemment). Lecture seule.",
  mcpTool: true,
  schema: z.object({
    adresses: emailListSchema.describe("Adresses du ou des destinataires à vérifier"),
  }),
  http: { method: "POST" },
  run: async ({ adresses }) => {
    const { stdout, stderr, exitCode } = await runScript("contact_guard.py", adresses);

    // contact_guard : 0 = OK, 1 = ATTENTION, 2 = BLOQUÉ.
    const verdict = exitCode === 0 ? "ok" : exitCode === 1 ? "attention" : exitCode === 2 ? "bloque" : "erreur";
    return {
      verdict,
      report: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
