#!/usr/bin/env python3
"""Prépare et affiche les meilleures offres d'alternance PASS prêtes pour la création de brouillons."""
import json
import os
import sys
from typing import Any, Dict, List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    in_file: str = os.path.join(ROOT, "state", "pass_alternance_scored.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord filter_alternance_pass.py.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    # Top 5 offres IA / Data / Tech en alternance
    top_offers: List[Dict[str, Any]] = []
    for o in offers:
        if o.get("contact_recruteur") and "@" in o["contact_recruteur"]:
            top_offers.append(o)

    print("Top 5 offres sélectionnées pour création de brouillons :\n")
    for i, o in enumerate(top_offers[:5], 1):
        print(f"[{i}] {o['poste']}")
        print(f"    - Administration : {o['entreprise']}")
        print(f"    - Destinataire    : {o['contact_recruteur']}")
        print(f"    - Réf. Offre     : {o.get('numero_offre', 'N/A')}")
        print(f"    - Durée          : {o.get('duree_contrat', '24 mois')}")
        print(f"    - Lien           : {o['lien']}\n")


if __name__ == "__main__":
    main()
