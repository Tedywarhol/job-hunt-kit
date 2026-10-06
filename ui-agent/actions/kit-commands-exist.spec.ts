import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { getWorkspaceRoot } from "../shared/hunt-bridge";

/**
 * The other specs mock the bridge, so they cannot notice an action that calls
 * a script or a hunt.py subcommand that does not exist (this is how
 * check-consistency and check-ats-coverage shipped broken). This one reads the
 * action sources and checks every command against the real kit.
 */
const actionsDir = __dirname;
const sources = readdirSync(actionsDir)
  .filter((file) => file.endsWith(".ts") && !file.endsWith(".spec.ts"))
  .map((file) => ({ file, text: readFileSync(path.join(actionsDir, file), "utf-8") }));

function collect(pattern: RegExp): Array<{ file: string; value: string }> {
  return sources.flatMap(({ file, text }) =>
    [...text.matchAll(pattern)].map((match) => ({ file, value: match[1] })),
  );
}

describe("commands called by the actions exist in the kit", () => {
  const root = getWorkspaceRoot();

  it("finds the scripts and subcommands the actions call", () => {
    expect(collect(/runScript\(\s*"([a-z0-9_]+\.py)"/g).length).toBeGreaterThan(0);
    expect(collect(/runHuntCommand\(\s*\[\s*"([a-z-]+)"/g).length).toBeGreaterThan(0);
  });

  it.each(collect(/runScript\(\s*"([a-z0-9_]+\.py)"/g))("script $value ($file)", ({ value }) => {
    expect(existsSync(path.join(root, "scripts", value))).toBe(true);
  });

  it.each(collect(/runHuntCommand\(\s*\[\s*"([a-z-]+)"/g))("hunt.py subcommand $value ($file)", ({ value }) => {
    const python = process.platform === "win32" ? "python" : "python3";
    expect(() =>
      execFileSync(python, ["hunt.py", value, "--help"], { cwd: root, stdio: "pipe" }),
    ).not.toThrow();
  });
});
