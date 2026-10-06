import { describe, expect, it, vi } from "vitest";
import action from "./check-ats-coverage";
import * as bridge from "../shared/hunt-bridge";

const ok = (stdout: string) => ({ stdout, stderr: "", exitCode: 0 });

describe("check-ats-coverage action", () => {
  it("checks one application folder when a slug is given", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue(ok("Couverture ATS : 85%"));

    const res = await action.run({ slug: "acme-data-engineer", all: false });
    expect(spy).toHaveBeenCalledWith("check_ats_coverage.py", ["acme-data-engineer"], expect.anything());
    expect(res.success).toBe(true);
    expect(res.report).toContain("85%");

    vi.restoreAllMocks();
  });

  it("checks every folder with the all flag, and when no slug is given", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue(ok("Tous les dossiers vérifiés"));

    await action.run({ all: true });
    await action.run({ all: false });
    expect(spy).toHaveBeenNthCalledWith(1, "check_ats_coverage.py", ["--all"], expect.anything());
    expect(spy).toHaveBeenNthCalledWith(2, "check_ats_coverage.py", ["--all"], expect.anything());

    vi.restoreAllMocks();
  });
});
