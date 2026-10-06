import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runScript } from "../shared/hunt-bridge";
import { slugSchema } from "../shared/schemas";

export default defineAction({
  description: "Vérifier la couverture des mots-clés ATS dans le texte visible du CV vs la couche cachée.",
  mcpTool: true,
  schema: z.object({
    slug: slugSchema.optional().describe("Slug spécifique de la candidature à analyser"),
    all: z.boolean().default(false).describe("Analyser l'ensemble des dossiers dans outputs/"),
  }),
  http: { method: "POST" },
  run: async ({ slug, all }) => {
    const args = all || !slug ? ["--all"] : [slug];
    const { stdout, stderr, exitCode } = await runScript("check_ats_coverage.py", args, { timeout: 90000 });

    return {
      success: exitCode === 0,
      report: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
