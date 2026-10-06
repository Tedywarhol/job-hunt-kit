import { defineAction } from "@agent-native/core/action";
import { z } from "zod";
import { runScript } from "../shared/hunt-bridge";

export default defineAction({
  description:
    "Contrôle de cohérence entre outputs/, state/outreach.json et Notion. Rapport seul : ne modifie rien.",
  mcpTool: true,
  schema: z.object({}),
  http: { method: "POST" },
  run: async () => {
    const { stdout, stderr, exitCode } = await runScript("check_consistency.py", [], { timeout: 90000 });

    return {
      success: exitCode === 0,
      report: stdout.trim(),
      stderr: stderr.trim() || undefined,
    };
  },
});
