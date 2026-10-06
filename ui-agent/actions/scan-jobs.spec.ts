import { describe, expect, it, vi } from "vitest";
import action from "./scan-jobs";
import * as bridge from "../shared/hunt-bridge";

describe("scan-jobs action", () => {
  it("forwards ats flag and returns output", async () => {
    const spy = vi.spyOn(bridge, "runHuntCommand").mockResolvedValue({
      stdout: "Scan complete: 12 new offers found",
      stderr: "",
      exitCode: 0,
    });

    const res = await action.run({ source: "ats" });
    expect(spy).toHaveBeenCalledWith(["scan", "--ats"], { timeout: 120000 });
    expect(res.success).toBe(true);
    expect(res.stdout).toContain("12 new offers found");

    vi.restoreAllMocks();
  });

  it("handles failure exit codes gracefully", async () => {
    vi.spyOn(bridge, "runHuntCommand").mockResolvedValue({
      stdout: "",
      stderr: "Network error occurred",
      exitCode: 1,
    });

    const res = await action.run({ source: "pass" });
    expect(res.success).toBe(false);
    expect(res.stderr).toBe("Network error occurred");

    vi.restoreAllMocks();
  });
});
