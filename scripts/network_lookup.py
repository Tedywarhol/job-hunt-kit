#!/usr/bin/env python3
"""Bases du réseau dans state/ : adresse probable d'une personne repérée sur LinkedIn (d'après le format d'adresse
déjà observé dans son entreprise) et opportunités désignées à la main.

Lit les bases produites par `scripts/network.py build` (`state/network.json` et les bases secondaires
`state/network-<nom>.json`), puis passe chaque adresse proposée au garde-fou des refus (`contact_guard`).
Point d'entrée : `python scripts/network.py adresse <entreprise|domaine> <Prénom> <Nom>`.
"""
import json
import os
import re
import sys
from glob import glob
from typing import Dict, List, Optional

import contact_guard
from network_patterns import FORMATS, build_address, plain

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK_PATH: str = os.path.join(ROOT, "state", "network.json")
CONFIDENCE_RANK = {"sûre": 2, "probable": 1, "inconnue": 0}


def find_domain(query: str, companies: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    wanted = plain(query)
    for company in companies:
        if wanted in (plain(company["domaine"]), plain(company["entreprise"])):
            return company
    return next((c for c in companies if wanted and wanted in plain(c["entreprise"] + c["domaine"])), None)


def network_files() -> List[str]:
    """Ma base, puis les bases secondaires `state/network-<nom>.json` (un proche qui cherche aussi), sans le cache Gmail
    ni les identifiants Notion."""
    extra = [p for p in sorted(glob(os.path.join(ROOT, "state", "network-*.json")))
             if not re.search(r"network-(gmail-cache|notion)", os.path.basename(p))]
    return [NETWORK_PATH] + extra


def known_companies() -> List[Dict[str, str]]:
    """Les formats d'adresse décrivent l'entreprise : on réunit toutes les bases présentes, en gardant pour chaque
    domaine la preuve la plus solide. Les refus, eux, restent ceux du candidat."""
    best: Dict[str, Dict[str, str]] = {}
    for path in network_files():
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for company in json.load(f).get("entreprises", []):
                current = best.get(company["domaine"])
                if current is None or CONFIDENCE_RANK[company["confiance"]] > CONFIDENCE_RANK[current["confiance"]]:
                    best[company["domaine"]] = company
    return list(best.values())


def guess(query: str, first: str, last: str) -> None:
    company = find_domain(query, known_companies())
    if company is None:
        sys.exit(f"Aucune entreprise connue pour « {query} » : pas d'adresse fiable à proposer.")
    formats = [company["format"]] if company["format"] else [fmt for fmt, _ in FORMATS[:3]]
    print(f"{company['entreprise']} ({company['domaine']}) : format {company['format'] or 'inconnu'}, confiance {company['confiance']}")
    if company["exemples"]:
        print(f"  exemples connus : {company['exemples']}")
    for fmt in formats:
        address = build_address(fmt, first, last, company["domaine"])
        verdict = contact_guard.check(address or "", contact_guard.load_refusals())
        flag = f"  [{verdict['niveau'].upper()} : {verdict['raison']}]" if verdict else ""
        print(f"  {address}  ({fmt}){flag}")


def manual_opportunities() -> List[str]:
    """Processus réels que les objets de mail ne trahissent pas : `state/opportunites-manuelles.json`, une liste
    d'adresses ou de domaines écrits « @domaine.fr » (données personnelles, jamais versionnées)."""
    path = os.path.join(ROOT, "state", "opportunites-manuelles.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [entry.strip().lower() for entry in json.load(f)]
