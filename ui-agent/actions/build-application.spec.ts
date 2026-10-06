import { describe, expect, it, vi } from "vitest";
import action from "./build-application";
import * as bridge from "../shared/hunt-bridge";

describe("build-application action", () => {
  it("rebuilds the PDFs with build_application.py, never with the interactive hunt apply", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({
      stdout: "CV : OK\nLettre : OK",
      stderr: "",
      exitCode: 0,
    });
    const hunt = vi.spyOn(bridge, "runHuntCommand");

    const res = await action.run({ slug: "acme-data-engineer", profile: "stage" });
    expect(spy).toHaveBeenCalledWith(
      "build_application.py",
      ["--slug", "acme-data-engineer", "--profile", "stage"],
      expect.anything(),
    );
    expect(hunt).not.toHaveBeenCalled();
    expect(res.success).toBe(true);
    expect(res.slug).toBe("acme-data-engineer");

    vi.restoreAllMocks();
  });

  it("reports the failure and its exit code when the folder has no variables yet", async () => {
    vi.spyOn(bridge, "runScript").mockResolvedValue({
      stdout: "",
      stderr: "Manque cv-vars.json : cv-tailor doit l'écrire d'abord.",
      exitCode: 1,
    });

    const res = await action.run({ slug: "inconnu-sans-vars", profile: "alternance" });
    expect(res.success).toBe(false);
    expect(res.exitCode).toBe(1);
    expect(res.stderr).toContain("cv-tailor");

    vi.restoreAllMocks();
  });
});
