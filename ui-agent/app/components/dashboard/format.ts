import type { FollowupDue } from "../../../shared/dashboard-types";

/** Trust levels, warmest first, in the order the kit defines them (network_patterns.TRUST_LEVELS). */
export const TRUST_ORDER = ["Opportunité", "Échange", "Réponse", "Refus", "Sans réponse"] as const;

/** Notion statuses, in funnel order (dashboard.ORDRE_STATUTS_AFFICHES). */
export const FUNNEL_ORDER = [
  "À traiter",
  "Postulé",
  "Entretien",
  "Offre reçue",
  "Réponse reçue",
  "Refusé",
  "Écartée",
] as const;

export type Tone = "late" | "today" | "soon";

export function relanceTone(jours: number): Tone {
  if (jours < 0) return "late";
  return jours === 0 ? "today" : "soon";
}

export function relanceLabel(jours: number): string {
  if (jours < 0) return `En retard de ${-jours} j`;
  if (jours === 0) return "Aujourd'hui";
  return `Dans ${jours} j`;
}

export interface Row {
  label: string;
  value: number;
}

/** Known labels first in the given order, then any other label by decreasing count. */
export function orderRows(counts: Record<string, number>, order: readonly string[]): Row[] {
  const known = order.filter((label) => (counts[label] ?? 0) > 0).map((label) => ({ label, value: counts[label] }));
  const others = Object.entries(counts)
    .filter(([label, value]) => !order.includes(label) && value > 0)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
  return [...known, ...others];
}

export function barWidth(value: number, max: number): string {
  if (max <= 0 || value <= 0) return "0%";
  return `${Math.max(4, Math.round((value / max) * 100))}%`;
}

export function groupRelances(relances: FollowupDue[]): { late: FollowupDue[]; today: FollowupDue[]; soon: FollowupDue[] } {
  return {
    late: relances.filter((r) => relanceTone(r.jours) === "late"),
    today: relances.filter((r) => relanceTone(r.jours) === "today"),
    soon: relances.filter((r) => relanceTone(r.jours) === "soon"),
  };
}

/** Same rule as hunt.py apply: the folder name is the slug of the offer. */
export function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
