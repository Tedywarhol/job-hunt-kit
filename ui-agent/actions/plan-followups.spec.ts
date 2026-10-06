import { describe, expect, it, vi } from "vitest";
import action from "./plan-followups";
import * as bridge from "../shared/hunt-bridge";

describe("plan-followups action", () => {
  it("runs the follow-up engine in dry-run only, never with --apply", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({
      stdout: "Acme Aero : préparerait un brouillon J+3",
      stderr: "",
      exitCode: 0,
    });

    const res = await action.run({});
    expect(spy).toHaveBeenCalledWith("run_followups.py", [], expect.anything());
    expect(spy.mock.calls[0][1]).not.toContain("--apply");
    expect(res.report).toContain("préparerait");

    vi.restoreAllMocks();
  });
});
