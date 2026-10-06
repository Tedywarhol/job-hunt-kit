import { describe, expect, it, vi } from "vitest";
import action from "./get-dashboard-stats";
import * as bridge from "../shared/hunt-bridge";

const payload = {
  genere_le: "2026-10-06",
  relances: [{ entreprise: "Acme Aero", poste: "Data", etape_suivante: "J+3", echeance: "2026-10-06", jours: 0 }],
  statuts_locaux: { "Brouillon créé": 1 },
  notion: null,
  fraicheur: { today: 0, week: 1, month: 2, older: 0 },
  offres: { en_attente: 2, meilleures: [] },
  dossiers: { total: 0, recents: [] },
  reseau: null,
};

describe("get-dashboard-stats action", () => {
  it("returns the JSON printed by ui_data.py, without Notion by default", async () => {
    const spy = vi
      .spyOn(bridge, "runScript")
      .mockResolvedValue({ stdout: JSON.stringify(payload), stderr: "", exitCode: 0 });

    const res = await action.run({ format: "json", notion: false });
    expect(spy).toHaveBeenCalledWith("ui_data.py", ["--sans-notion"], expect.anything());
    expect(res).toEqual(payload);

    vi.restoreAllMocks();
  });

  it("asks for the real Notion statuses when notion is true", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({ stdout: JSON.stringify(payload), stderr: "", exitCode: 0 });

    await action.run({ format: "json", notion: true });
    expect(spy).toHaveBeenCalledWith("ui_data.py", [], expect.anything());

    vi.restoreAllMocks();
  });

  it("asks for the fictional demo data when HUNT_UI_DEMO=1, whatever the notion flag", async () => {
    const spy = vi.spyOn(bridge, "runScript").mockResolvedValue({ stdout: JSON.stringify(payload), stderr: "", exitCode: 0 });
    vi.stubEnv("HUNT_UI_DEMO", "1");

    await action.run({ format: "json", notion: true });
    expect(spy).toHaveBeenCalledWith("ui_data.py", ["--demo"], expect.anything());

    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("fails loudly instead of showing wrong numbers when the script fails or prints garbage", async () => {
    const spy = vi.spyOn(bridge, "runScript");

    spy.mockResolvedValueOnce({ stdout: "", stderr: "Traceback boom", exitCode: 1 });
    await expect(action.run({ format: "json", notion: false })).rejects.toThrow(/Traceback boom/);

    spy.mockResolvedValueOnce({ stdout: "pas du json", stderr: "", exitCode: 0 });
    await expect(action.run({ format: "json", notion: false })).rejects.toThrow(/JSON valide/);

    vi.restoreAllMocks();
  });

  it("calls hunt stats when format is text", async () => {
    vi.spyOn(bridge, "runHuntCommand").mockResolvedValue({
      stdout: "=== DASHBOARD STATS ===",
      stderr: "",
      exitCode: 0,
    });

    const res = await action.run({ format: "text", notion: false });
    if (!("output" in res)) {
      throw new Error("Expected text response");
    }
    expect(res.output).toContain("DASHBOARD STATS");

    vi.restoreAllMocks();
  });
});
