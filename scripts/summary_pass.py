#!/usr/bin/env python3
"""Analyse et synthétise les 130 offres PASS scrappées."""
from collections import Counter
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    in_file: str = os.path.join(ROOT, "state", "pass_offers_enriched.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord enrich_pass_offers.py.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    print(f"Total offres scrappées: {len(offers)}")

    # Breakdown by domain
    domain_counts = Counter(o.get("domaine", "Inconnu") for o in offers)
    print("\n--- Répartition par Domaine ---")
    for d, c in domain_counts.most_common():
        print(f"  * {d}: {c}")

    # Breakdown by Contract Type
    type_counts = Counter(o.get("type_contrat", "Inconnu") for o in offers)
    print("\n--- Répartition par Type de Contrat ---")
    for t, c in type_counts.most_common():
        print(f"  * {t}: {c}")

    # Breakdown by Diploma Level
    diploma_counts = Counter(o.get("niveau_diplome", "Inconnu") for o in offers)
    print("\n--- Répartition par Niveau de Diplôme ---")
    for d, c in diploma_counts.most_common():
        print(f"  * {d}: {c}")

    # Contact emails presence
    with_email = [o for o in offers if o.get("contact_emails")]
    pct = (len(with_email) / len(offers) * 100) if offers else 0
    print("\n--- Contacts Recruteurs Directs ---")
    print(f"  * Offres avec email direct de contact: {len(with_email)} / {len(offers)} ({pct:.1f}%)")

    # Specific Data / IA / GenAI / Tech highlights
    print("\n--- Zoom sur les offres Data / IA / GenAI / Tech ---")
    data_ia_offers: List[Tuple[int, Dict[str, Any]]] = []
    for o in offers:
        score = 0
        titre_lower = str(o.get("titre", "")).lower()
        if any(k in titre_lower for k in ["data", "ia", "intelligence artificielle", "machine learning", "ia frugale", "data engineer", "data scientist", "data analyst"]):
            score += 3
        if any(k in titre_lower for k in ["développeur", "full stack", "si", "automatisation", "innovation", "digital"]):
            score += 2
        if score > 0:
            data_ia_offers.append((score, o))

    data_ia_offers.sort(key=lambda x: x[0], reverse=True)
    print(f"Total offres pertinentes Data/IA/Tech: {len(data_ia_offers)}")
    for score, o in data_ia_offers[:25]:
        emails = ", ".join(o.get("contact_emails", [])) or "Formulaire / N/A"
        print(f"- [{o.get('type_contrat')}] {o.get('titre')} | {o.get('recruteur')} ({o.get('niveau_diplome')}) -> Contact: {emails}")


if __name__ == "__main__":
    main()
