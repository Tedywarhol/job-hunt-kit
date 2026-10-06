import { describe, expect, it, vi } from "vitest";
import action from "./check-contact";
import * as bridge from "../shared/hunt-bridge";

describe("check-contact action", () => {
  it.each([
    [0, "ok"],
    [1, "attention"],
    [2, "bloque"],
    [3, "erreur"],
  ])("maps the guard exit code %i to the verdict %s", async (exitCode, verdict) => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({ stdout: "BLOQUÉ x", stderr: "", exitCode });

    const res = await action.run({ adresses: ["agent@conseil-exemple.com"] });
    expect(spy).toHaveBeenCalledWith("contact_guard.py", ["agent@conseil-exemple.com"]);
    expect(res.verdict).toBe(verdict);

    vi.restoreAllMocks();
  });
});
