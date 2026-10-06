import { describe, expect, it, vi } from "vitest";
import action from "./check-consistency";
import * as bridge from "../shared/hunt-bridge";

describe("check-consistency action", () => {
  it("runs the consistency script and returns its report", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({
      stdout: "✅ Tout est cohérent",
      stderr: "",
      exitCode: 0,
    });

    const res = await action.run({});
    expect(spy).toHaveBeenCalledWith("check_consistency.py", [], expect.anything());
    expect(res.success).toBe(true);
    expect(res.report).toContain("Tout est cohérent");

    vi.restoreAllMocks();
  });
});
