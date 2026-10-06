import { existsSync, readdirSync } from "node:fs";
import path from "node:path";
import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { getWorkspaceRoot, runScript } from "../shared/hunt-bridge";
import { slugSchema } from "../shared/schemas";

export default defineAction({
  description:
    "Régénérer les PDF (CV + lettre de motivation) d'un dossier de candidature existant sous outputs/<slug>. Le dossier doit déjà contenir cv-vars.json et lettre-vars.json (écrits par l'agent cv-tailor) : sinon l'action échoue sans rien créer. Ne lit aucune entrée au clavier et n'ouvre aucun fichier.",
  mcpTool: true,
  schema: z.object({
    slug: slugSchema.describe("Nom du dossier de l'offre sous outputs/ (ex: acme-data-engineer)"),
    profile: z.enum(["alternance", "stage"]).default("alternance").describe("Type de profil candidat"),
  }),
  http: { method: "POST" },
  run: async ({ slug, profile }) => {
    // build_application.py, not `hunt.py apply` : ce dernier pose une question interactive à la fin
    // (« Ouvrir les PDF ? ») qui bloquerait ici jusqu'au délai maximal, et il ouvrirait les PDF sur l'écran.
    const { stdout, stderr, exitCode } = await runScript(
      "build_application.py",
      ["--slug", slug, "--profile", profile],
      { timeout: 120000 },
    );

    const outputDir = path.join(getWorkspaceRoot(), "outputs", slug);
    const files = existsSync(outputDir) ? readdirSync(outputDir) : [];

    return {
      success: exitCode === 0,
      exitCode,
      slug,
      profile,
      files,
      stdout: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
