import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { getWorkspaceRoot, readWorkspaceJson, runScript } from "./hunt-bridge";

describe("hunt-bridge", () => {
  it("resolves the workspace root that really contains hunt.py", () => {
    expect(existsSync(path.join(getWorkspaceRoot(), "hunt.py"))).toBe(true);
  });

  it("resolves the root from any working directory, without __dirname (ES module at runtime)", () => {
    const cwd = vi.spyOn(process, "cwd").mockReturnValue(path.parse(process.cwd()).root);
    try {
      expect(existsSync(path.join(getWorkspaceRoot(), "hunt.py"))).toBe(true);
    } finally {
      cwd.mockRestore();
    }
  });

  it("reads existing workspace json files safely", () => {
    const data = readWorkspaceJson("templates/cv/cv-data.template.json");
    expect(data).not.toBeNull();
  });

  it("returns null for non-existent json files", () => {
    const data = readWorkspaceJson("state/non-existent-file-12345.json");
    expect(data).toBeNull();
  });

  it("runs a kit script and keeps stdout and the exit code of a failing one", async () => {
    const res = await runScript("contact_guard.py", ["inconnu@exemple.invalid"]);
    expect(typeof res.exitCode).toBe("number");
    expect(typeof res.stdout).toBe("string");
  });

  it("refuses a script name that is a path, so nothing outside scripts/ can run", () => {
    expect(() => runScript("../hunt.py")).toThrow(/Invalid script name/);
    expect(() => runScript("scripts/network.py")).toThrow(/Invalid script name/);
    expect(() => runScript("network.sh")).toThrow(/Invalid script name/);
  });
});
