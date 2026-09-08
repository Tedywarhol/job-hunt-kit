#!/usr/bin/env python3
"""Analyse rétroactive du taux de réponse par ATS / source / score (E4, exploratoire).

Les données existent déjà dans Notion (Statut, ATS, Source, Score) mais n'étaient
exploitées nulle part pour orienter le ciblage — cf. docs/plans/2026-09-07-plan-
amelioration.md. Lecture seule : ce script n'écrit jamais rien.

« Taux de réponse » = part des candidatures Postulé (ou au-delà) ayant reçu une réaction
du recruteur, positive ou négative (Entretien, Offre reçue, Réponse reçue, Refusé) — pas
seulement les réponses positives, pour ne pas fausser le signal.

Usage:
  python scripts/analyze_response_rates.py
"""
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import push_notion as pn

REPONSE_STATUTS = {"Entretien", "Offre reçue", "Réponse reçue", "Refusé"}
POSTULE_STATUTS = {"Postulé"} | REPONSE_STATUTS

SCORE_BUCKETS: List[Tuple[str, int, int]] = [
    ("90-100", 90, 101), ("80-89", 80, 90), ("70-79", 70, 80), ("<70", 0, 70),
]


def extract_rows(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for pg in pages:
        props = pg.get("properties", {})
        rows.append({
            "statut": pn.prop_select(props, "Statut"),
            "ats": pn.prop_select(props, "ATS") or "(inconnu)",
            "source": pn.prop_select(props, "Source") or "(inconnu)",
            "score": (props.get("Score", {}) or {}).get("number"),
        })
    return rows


def _rate(postule: int, reponse: int) -> float:
    return round(100 * reponse / postule, 1) if postule else 0.0


def group_stats(rows: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    """Regroupe les lignes réellement postulées par `key` (ats|source), calcule le taux."""
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"postule": 0, "reponse": 0})
    for r in rows:
        if r["statut"] not in POSTULE_STATUTS:
            continue
        g = groups[r[key]]
        g["postule"] += 1
        if r["statut"] in REPONSE_STATUTS:
            g["reponse"] += 1
    return {g: {**c, "taux_pct": _rate(c["postule"], c["reponse"])} for g, c in groups.items()}


def score_bucket_stats(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    counts: Dict[str, Dict[str, int]] = {label: {"postule": 0, "reponse": 0} for label, _, _ in SCORE_BUCKETS}
    for r in rows:
        if r["statut"] not in POSTULE_STATUTS or r["score"] is None:
            continue
        for label, lo, hi in SCORE_BUCKETS:
            if lo <= r["score"] < hi:
                counts[label]["postule"] += 1
                if r["statut"] in REPONSE_STATUTS:
                    counts[label]["reponse"] += 1
                break
    return {g: {**c, "taux_pct": _rate(c["postule"], c["reponse"])} for g, c in counts.items()}


def render_group(title: str, stats: Dict[str, Dict[str, Any]]) -> str:
    lines = [f"\n{title} :"]
    for g, c in sorted(stats.items(), key=lambda kv: kv[1]["postule"], reverse=True):
        if c["postule"] == 0:
            continue
        lines.append(f"  {g:<20} : {c['reponse']}/{c['postule']} réponses ({c['taux_pct']}%)")
    if len(lines) == 1:
        lines.append("  (pas assez de données)")
    return "\n".join(lines)


def load_notion_pages() -> Optional[List[Dict[str, Any]]]:
    try:
        cfg = pn.load_cfg()
        db_id = pn.database_id_from_url(cfg["database_url"])
        token = pn.get_token()
        return pn.fetch_all_pages(token, db_id)
    except (SystemExit, FileNotFoundError):
        return None


def main() -> None:
    pages = load_notion_pages()
    if pages is None:
        sys.exit("Notion non configuré — impossible d'analyser le taux de réponse.")

    rows = extract_rows(pages)
    total_postule = sum(1 for r in rows if r["statut"] in POSTULE_STATUTS)
    total_reponse = sum(1 for r in rows if r["statut"] in REPONSE_STATUTS)

    print("\n" + "=" * 60)
    print("ANALYSE RÉTROACTIVE — TAUX DE RÉPONSE")
    print("=" * 60)
    print(f"\nGlobal : {total_reponse}/{total_postule} réponses ({_rate(total_postule, total_reponse)}%)")

    print(render_group("Par ATS", group_stats(rows, "ats")))
    print(render_group("Par source", group_stats(rows, "source")))
    print(render_group("Par tranche de score", score_bucket_stats(rows)))

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
