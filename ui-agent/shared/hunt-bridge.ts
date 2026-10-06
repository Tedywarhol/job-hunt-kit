import { execFile } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/**
 * Resolves the root workspace directory containing hunt.py.
 *
 * The package is an ES module: `__dirname` does not exist at runtime (it only
 * worked under Vitest, which shims it), so the module location comes from
 * `import.meta.url`. HUNT_WORKSPACE_ROOT overrides the search.
 */
export function getWorkspaceRoot(): string {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const candidates = [
    process.env.HUNT_WORKSPACE_ROOT,
    process.cwd(),
    path.resolve(process.cwd(), ".."),
    path.resolve(here, ".."),
    path.resolve(here, "../.."),
  ].filter((dir): dir is string => Boolean(dir));

  for (const dir of candidates) {
    if (existsSync(path.join(dir, "hunt.py"))) {
      return path.resolve(dir);
    }
  }

  // Fallback to parent directory
  return path.resolve(process.cwd(), "..");
}

export interface HuntExecutionResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/**
 * Runs `python <args>` inside the root workspace. A non-zero exit is a result,
 * not an exception: the guard scripts use exit codes 1 and 2 for warnings.
 */
async function runPython(
  args: string[],
  options: { timeout?: number } = {},
): Promise<HuntExecutionResult> {
  const pythonCmd = process.platform === "win32" ? "python" : "python3";

  try {
    const { stdout, stderr } = await execFileAsync(pythonCmd, args, {
      cwd: getWorkspaceRoot(),
      timeout: options.timeout ?? 60000,
      maxBuffer: 16 * 1024 * 1024,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
      },
    });
    return {
      stdout: stdout.toString(),
      stderr: stderr.toString(),
      exitCode: 0,
    };
  } catch (err: unknown) {
    const execErr = err as { stdout?: string; stderr?: string; code?: number; message?: string };
    return {
      stdout: execErr.stdout?.toString() ?? "",
      stderr: execErr.stderr?.toString() ?? execErr.message ?? String(err),
      exitCode: typeof execErr.code === "number" ? execErr.code : 1,
    };
  }
}

/**
 * Executes a hunt.py command inside the root workspace.
 */
export function runHuntCommand(
  args: string[],
  options: { timeout?: number } = {},
): Promise<HuntExecutionResult> {
  return runPython(["hunt.py", ...args], options);
}

/**
 * Executes a script of the kit (scripts/<name>) that hunt.py does not expose.
 * The name is a file name, never a path: it cannot leave the scripts folder.
 */
export function runScript(
  name: string,
  args: string[] = [],
  options: { timeout?: number } = {},
): Promise<HuntExecutionResult> {
  if (!/^[a-z0-9_]+\.py$/.test(name)) {
    throw new Error(`Invalid script name: ${name}`);
  }
  return runPython([path.join("scripts", name), ...args], options);
}

/**
 * Safely reads and parses a JSON file relative to the root workspace.
 */
export function readWorkspaceJson<T = unknown>(relativePath: string): T | null {
  const rootDir = getWorkspaceRoot();
  const filePath = path.join(rootDir, relativePath);

  if (!existsSync(filePath)) {
    return null;
  }

  try {
    const raw = readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}
