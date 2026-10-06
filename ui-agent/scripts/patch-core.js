import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const coreDist = path.resolve(__dirname, "../node_modules/@agent-native/core/dist/cli");

if (!fs.existsSync(coreDist)) {
  process.exit(0);
}

// 1. Patch react-router-command.js
const rrCommandPath = path.join(coreDist, "react-router-command.js");
if (fs.existsSync(rrCommandPath)) {
  let content = fs.readFileSync(rrCommandPath, "utf-8");
  
  // Patch findBinUpwards for .cmd on Windows
  if (!content.includes(".cmd`")) {
    content = content.replace(
      'for (let i = 0; i < 20; i++) {',
      'for (let i = 0; i < 20; i++) {\n        if (process.platform === "win32") {\n            const cmdCandidate = path.join(dir, "node_modules", ".bin", `${binName}.cmd`);\n            if (fs.existsSync(cmdCandidate))\n                return cmdCandidate;\n        }',
    );
  }
  
  // Patch findReactRouterInvocation to use direct JS entry
  if (!content.includes("pkg.bin?.[\"react-router\"]")) {
    content = content.replace(
      'export function findReactRouterInvocation(args, cwd = process.cwd()) {',
      `export function findReactRouterInvocation(args, cwd = process.cwd()) {
    try {
        const require = createRequire(path.join(cwd, "package.json"));
        const pkgJsonPath = require.resolve("@react-router/dev/package.json");
        const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, "utf-8"));
        const rel = typeof pkg.bin === "string" ? pkg.bin : pkg.bin?.["react-router"];
        if (rel) {
            const entry = path.resolve(path.dirname(pkgJsonPath), rel);
            if (fs.existsSync(entry)) {
                return {
                    command: process.execPath,
                    args: [entry, ...args],
                    shell: false,
                };
            }
        }
    } catch {}`,
    );
  }
  
  fs.writeFileSync(rrCommandPath, content, "utf-8");
}

// 2. Patch cli/index.js
const indexPath = path.join(coreDist, "index.js");
if (fs.existsSync(indexPath)) {
  let content = fs.readFileSync(indexPath, "utf-8");
  
  // Patch run function
  if (!content.includes('const isNode = cmd === process.execPath || cmd === "node";')) {
    content = content.replace(
      'function run(cmd, cmdArgs, opts) {',
      'function run(cmd, cmdArgs, opts) {\n    const isNode = cmd === process.execPath || cmd === "node";\n    if (isNode && opts?.shell === undefined) opts = { ...opts, shell: false };',
    );
  }

  // Patch dev command to use viteJsEntry directly
  if (!content.includes('const viteJsEntry = findViteJsEntry();\n        const vite = viteJsEntry ? process.execPath : findViteBin();')) {
    content = content.replace(
      'const vite = findViteBin();\n        const { inspectFlag, rest } = extractNodeInspectFlag(args);\n        if (!inspectFlag) {\n            run(vite, rest);',
      'const viteJsEntry = findViteJsEntry();\n        const vite = viteJsEntry ? process.execPath : findViteBin();\n        const { inspectFlag, rest } = extractNodeInspectFlag(args);\n        const finalViteArgs = viteJsEntry ? [viteJsEntry, ...rest] : rest;\n        if (!inspectFlag) {\n            run(vite, finalViteArgs, { shell: !viteJsEntry && process.platform === "win32" });',
    );
  }

  // Patch runBuildStep function for Windows space quoting
  if (!content.includes('const isShell = opts.shell ?? false;')) {
    content = content.replace(
      'const finalCmd = process.platform === "win32" && typeof cmd === "string" && cmd.includes(" ") && !cmd.startsWith(\'"\')\n            ? `"${cmd}"`\n            : cmd;\n        const child = spawn(finalCmd, cmdArgs, {\n            stdio: ["inherit", "pipe", "pipe"],\n            shell: opts.shell ?? process.platform === "win32",\n            env: opts.env ?? process.env,\n        });',
      'const isShell = opts.shell ?? (typeof cmd === "string" && cmd.endsWith(".cmd"));\n        const finalCmd = isShell && typeof cmd === "string" && cmd.includes(" ") && !cmd.startsWith(\'"\')\n            ? `"${cmd}"`\n            : cmd;\n        const child = spawn(finalCmd, cmdArgs, {\n            stdio: ["inherit", "pipe", "pipe"],\n            shell: isShell,\n            env: opts.env ?? process.env,\n        });',
    );
  }

  fs.writeFileSync(indexPath, content, "utf-8");
}

// 3. Patch deploy/build.js for Windows esbuild execution
const deployBuildPath = path.resolve(__dirname, "../node_modules/@agent-native/core/dist/deploy/build.js");
if (fs.existsSync(deployBuildPath)) {
  let content = fs.readFileSync(deployBuildPath, "utf-8");
  if (!content.includes("_origExecFileSync")) {
    content = content.replace(
      'import { execFileSync } from "child_process";',
      `import { execFileSync as _origExecFileSync } from "child_process";
const execFileSync = (file, args, options) => {
  if (process.platform === "win32" && typeof file === "string" && !file.endsWith(".exe") && !file.endsWith(".cmd")) {
    return _origExecFileSync(process.execPath, [file, ...(args || [])], options);
  }
  return _origExecFileSync(file, args, options);
};`,
    );
    fs.writeFileSync(deployBuildPath, content, "utf-8");
  }
}

console.log("[patch-core] @agent-native/core CLI successfully patched for Windows spaces support.");
