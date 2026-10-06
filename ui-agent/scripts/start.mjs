/**
 * Démarre la version construite (`pnpm build`) en chargeant d'abord `.env`.
 *
 * `agent-native start` ne lit pas `.env` : sans ce chargement, BETTER_AUTH_SECRET, AUTH_DISABLED,
 * les réglages Ollama ou HUNT_UI_DEMO ne seraient pas vus par le serveur, qui se verrouillerait.
 * Les variables déjà présentes dans l'environnement gardent la priorité (PORT=3056 pnpm start).
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const envFile = path.join(root, ".env");
const coreDir = path.join(root, "node_modules", "@agent-native", "core");

if (!existsSync(path.join(root, ".output", "server", "index.mjs"))) {
  console.error("Aucune version construite : lancez d'abord `pnpm build`.");
  process.exit(1);
}

if (existsSync(envFile)) {
  const shellEnv = { ...process.env };
  process.loadEnvFile(envFile);
  Object.assign(process.env, shellEnv);
}

const pkg = JSON.parse(readFileSync(path.join(coreDir, "package.json"), "utf-8"));
const bin = typeof pkg.bin === "string" ? pkg.bin : pkg.bin?.["agent-native"];
if (!bin) {
  console.error("Binaire agent-native introuvable : lancez `pnpm install`.");
  process.exit(1);
}

const child = spawn(process.execPath, [path.resolve(coreDir, bin), "start", ...process.argv.slice(2)], {
  cwd: root,
  stdio: "inherit",
  env: process.env,
});
child.on("exit", (code) => process.exit(code ?? 0));
