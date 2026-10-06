import { describe, expect, it, vi } from "vitest";
import action from "./guess-address";
import * as bridge from "../shared/hunt-bridge";

describe("guess-address action", () => {
  it("asks network.py for the probable address of a person", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({
      stdout: "laura.blanc@exemplia.fr (format prenom.nom, confiance élevée)",
      stderr: "",
      exitCode: 0,
    });

    const res = await action.run({ entreprise: "Exemplia", prenom: "Laura", nom: "Blanc" });
    expect(spy).toHaveBeenCalledWith("network.py", ["adresse", "Exemplia", "Laura", "Blanc"]);
    expect(res.success).toBe(true);
    expect(res.report).toContain("laura.blanc@exemplia.fr");

    vi.restoreAllMocks();
  });
});
