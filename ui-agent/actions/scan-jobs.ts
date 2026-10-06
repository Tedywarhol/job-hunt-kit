import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runHuntCommand } from "../shared/hunt-bridge";

export default defineAction({
  description: "Lancer le scan automatique du radar d'offres (ATS Greenhouse/Lever/Ashby et/ou PASS Fonction Publique).",
  mcpTool: true,
  schema: z.object({
    source: z.enum(["ats", "pass", "all"]).default("ats").describe("Source à scanner : ats, pass, ou all"),
  }),
  http: { method: "POST" },
  run: async ({ source }) => {
    const args: string[] = ["scan"];
    if (source === "ats") {
      args.push("--ats");
    } else if (source === "pass") {
      args.push("--pass");
    }

    const { stdout, stderr, exitCode } = await runHuntCommand(args, { timeout: 120000 });

    return {
      success: exitCode === 0,
      source,
      stdout: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
