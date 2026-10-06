import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The chat only offers the Ollama models listed in @agent-native/core, which are not
 * the ones installed locally. scripts/patch-core.js (run by `pnpm install`) makes that
 * list read OLLAMA_MODELS and OLLAMA_DEFAULT_MODEL. Each case runs in a fresh Node
 * process: the list is built once, when the module is first imported.
 */
const configModule = path.resolve(__dirname, "../node_modules/@agent-native/core/dist/agent/model-config.js");

function ollamaConfig(env: Record<string, string>): { defaultModel: string; supportedModels: string[] } {
  const code = `import(${JSON.stringify(`file:///${configModule.replace(/\\/g, "/")}`)})
    .then((m) => console.log(JSON.stringify(m.AI_SDK_MODEL_CONFIG.ollama)))`;
  const stdout = execFileSync(process.execPath, ["--input-type=module", "-e", code], {
    env: { PATH: process.env.PATH ?? "", ...env },
    encoding: "utf-8",
  });
  return JSON.parse(stdout);
}

describe("Ollama models of the chat", () => {
  it("offers the models listed in OLLAMA_MODELS, before the package defaults", () => {
    const config = ollamaConfig({ OLLAMA_MODELS: "gemma3:4b, qwen2.5:3b" });
    expect(config.supportedModels.slice(0, 2)).toEqual(["gemma3:4b", "qwen2.5:3b"]);
    expect(config.supportedModels).toContain("mistral");
  });

  it("does not list a model twice, and ignores empty entries", () => {
    const config = ollamaConfig({ OLLAMA_MODELS: "mistral,,gemma3:4b," });
    expect(config.supportedModels.filter((model) => model === "mistral")).toHaveLength(1);
    expect(config.supportedModels).not.toContain("");
  });

  it("takes the default model from OLLAMA_DEFAULT_MODEL", () => {
    expect(ollamaConfig({ OLLAMA_DEFAULT_MODEL: "qwen3.5:9b" }).defaultModel).toBe("qwen3.5:9b");
  });

  it("keeps the package list and default when nothing is set", () => {
    expect(ollamaConfig({})).toEqual({
      defaultModel: "llama3.1",
      supportedModels: ["llama3.1", "llama3.2", "mistral", "codestral"],
    });
  });
});
