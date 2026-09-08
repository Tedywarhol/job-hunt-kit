#!/usr/bin/env python3
"""Diagnostic de config/companies.yaml : teste si chaque board ATS répond réellement.

Découverte du 2026-09-07 : le retour visuel ajouté au scan (N5, plan d'amélioration) a
révélé que 30 des 48 entreprises listées (62%) renvoient 404 sur le board ATS supposé —
totalement silencieux auparavant (`fetch_json` avalait l'erreur avant le correctif M4).
Ces entrées ne remontent jamais aucune offre sans jamais le signaler.

Ce script ne corrige RIEN automatiquement : deviner un slug de board plausible serait une
donnée inventée, contraire à la discipline du projet (« ne devine jamais une clé d'API, un
nom de fichier »). Il mesure et rapporte, pour une vérification manuelle entreprise par
entreprise (ou via recherche web) avant toute correction de config/companies.yaml.

Usage:
  python scripts/check_companies_yaml.py
"""
import os
import sys
from typing import Any, Dict, List, Optional

import yaml

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_ats_api import fetch_json


def endpoint_for(comp: Dict[str, Any]) -> Optional[str]:
    ats = (comp.get("ats") or "").lower()
    url = comp.get("careers_url", "")
    slug = url.rstrip("/").split("/")[-1]
    if ats == "greenhouse" or "greenhouse.io" in url:
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    if ats == "lever" or "lever.co" in url:
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if ats == "ashby" or "ashbyhq.com" in url:
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    return None


def check_company(comp: Dict[str, Any]) -> Dict[str, Any]:
    name = comp.get("nom", "Inconnu")
    endpoint = endpoint_for(comp)
    if endpoint is None:
        return {"nom": name, "statut": "non-api", "endpoint": comp.get("careers_url", "")}
    data = fetch_json(endpoint)
    return {"nom": name, "statut": "OK" if data is not None else "BROKEN", "endpoint": endpoint}


def main() -> None:
    cfg_path = os.path.join(ROOT, "config", "companies.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    companies: List[Dict[str, Any]] = cfg.get("entreprises", [])

    print("\n" + "=" * 70)
    print("DIAGNOSTIC config/companies.yaml — boards ATS réellement joignables")
    print("=" * 70 + "\n")

    ok_count, broken_count, skipped = 0, 0, 0
    broken: List[Dict[str, Any]] = []
    for i, comp in enumerate(companies, 1):
        print(f"  [{i}/{len(companies)}] {comp.get('nom', '?')}...{'':<20}", end="\r", flush=True)
        result = check_company(comp)
        if result["statut"] == "OK":
            ok_count += 1
        elif result["statut"] == "BROKEN":
            broken_count += 1
            broken.append(result)
        else:
            skipped += 1
    print(" " * 60, end="\r")

    print(f"✅ {ok_count} joignable(s)")
    print(f"⚪ {skipped} sans API directe (scraping web, non testé ici)")
    print(f"❌ {broken_count} board(s) introuvable(s) (404) — slug probablement obsolète :\n")
    for b in broken:
        print(f"    - {b['nom']} : {b['endpoint']}")

    if broken:
        print(
            f"\nCes {broken_count} entrées ne remontaient jamais aucune offre sans jamais le "
            "signaler (silencieux avant le correctif M4 de l'audit du 2026-09-07). Vérifiez le "
            "bon token de board sur la page carrières réelle de chaque entreprise avant de "
            "corriger config/companies.yaml — ne devinez pas un slug plausible, il peut être faux."
        )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
