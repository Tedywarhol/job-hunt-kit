#!/usr/bin/env python3
"""Génère un export CSV clair des 130 offres PASS scrappées."""
import csv
import json
import os
import sys
from typing import Any, Dict, List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    in_file: str = os.path.join(ROOT, "state", "pass_offers_enriched.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord enrich_pass_offers.py.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    csv_file: str = os.path.join(ROOT, "state", "pass_offres_ile_de_france.csv")
    fieldnames: List[str] = [
        "titre",
        "type_contrat",
        "domaine",
        "recruteur",
        "administration",
        "niveau_diplome",
        "date_publication",
        "date_debut",
        "duree_contrat",
        "localisation",
        "contact_emails",
        "lien",
        "numero_offre",
    ]

    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for o in offers:
            row: Dict[str, Any] = dict(o)
            row["contact_emails"] = ", ".join(o.get("contact_emails", []))
            writer.writerow(row)

    print(f"Exporté {len(offers)} offres dans {csv_file}")


if __name__ == "__main__":
    main()
