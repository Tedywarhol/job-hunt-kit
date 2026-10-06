import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runScript } from "../shared/hunt-bridge";

export default defineAction({
  description:
    "Adresse email probable d'une personne repérée dans une entreprise déjà connue du réseau (format prénom.nom, etc.), avec le niveau de confiance du format et le garde-fou des refus. Une adresse devinée n'est jamais garantie : à envoyer d'abord à une seule personne.",
  mcpTool: true,
  schema: z.object({
    entreprise: z.string().min(2).max(120).describe("Nom de l'entreprise ou son domaine"),
    prenom: z.string().min(1).max(60),
    nom: z.string().min(1).max(60),
  }),
  http: { method: "POST" },
  run: async ({ entreprise, prenom, nom }) => {
    const { stdout, stderr, exitCode } = await runScript("network.py", ["adresse", entreprise, prenom, nom]);

    return {
      success: exitCode === 0,
      report: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
