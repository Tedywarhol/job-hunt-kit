#!/usr/bin/env python3
"""Envoie le réseau de contacts (state/network.json) dans deux bases Notion : « Contacts » et
« Entreprises et formats d'adresse », rangées dans une page partagée avec l'intégration du projet.

Usage :
  python scripts/network_notion.py --page <URL ou id de la page>   # première fois : crée les deux bases
  python scripts/network_notion.py                                  # ensuite : met à jour (une ligne par adresse / domaine)

Prérequis : dans Notion, la page choisie doit être partagée avec l'intégration (menu « ... » > Connexions).
"""
import argparse
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import push_notion as pn
from network_patterns import FORMATS, TRUST_LEVELS

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK_PATH: str = os.path.join(ROOT, "state", "network.json")
IDS_PATH: str = os.path.join(ROOT, "state", "network-notion.json")
API: str = "https://api.notion.com/v1"
PAUSE_S: float = 0.35  # l'API Notion accepte environ 3 requêtes par seconde

CONTACT_PROPS: Dict[str, Any] = {
    "Nom complet": {"title": {}}, "Prénom": {"rich_text": {}}, "Nom": {"rich_text": {}},
    "Entreprise": {"rich_text": {}}, "Email": {"email": {}}, "Téléphone": {"phone_number": {}},
    "Fonction": {"rich_text": {}},
    "Niveau de confiance": {"select": {"options": [{"name": n} for n in TRUST_LEVELS.values()]}}, "Priorité": {"number": {}},
    "Adresse": {"select": {"options": [{"name": n} for n in ("vérifiée", "délivrée", "invalide", "relais ATS", "citée")]}},
    "Relation": {"select": {"options": [{"name": n} for n in ("a répondu", "a refusé", "réponse automatique", "sans réponse")]}},
    "Premier échange": {"date": {}}, "Dernier échange": {"date": {}},
    "Mails envoyés": {"number": {}}, "Mails reçus": {"number": {}}, "Dernier sujet": {"rich_text": {}},
    "Source": {"select": {"options": [{"name": "échange"}, {"name": "contact partagé"}]}}, "Cité par": {"rich_text": {}},
}
COMPANY_PROPS: Dict[str, Any] = {
    "Entreprise": {"title": {}}, "Domaine": {"rich_text": {}},
    "Format d'adresse": {"select": {"options": [{"name": fmt} for fmt, _ in FORMATS]}},
    "Confiance": {"select": {"options": [{"name": n} for n in ("sûre", "probable", "inconnue")]}},
    "Exemples": {"rich_text": {}}, "Contacts": {"number": {}},
    "Adresses génériques": {"rich_text": {}}, "Adresses invalides": {"rich_text": {}},
}


def text(value: str) -> Dict[str, Any]:
    return {"rich_text": [{"text": {"content": value[:1990]}}]} if value else {"rich_text": []}


def contact_properties(c: Dict[str, str]) -> Dict[str, Any]:
    full = f"{c['prenom']} {c['nom']}".strip() or c["email"]
    props: Dict[str, Any] = {
        "Nom complet": {"title": [{"text": {"content": full}}]}, "Prénom": text(c["prenom"]), "Nom": text(c["nom"]),
        "Entreprise": text(c["entreprise"]), "Email": {"email": c["email"]}, "Fonction": text(c["fonction"]),
        "Téléphone": {"phone_number": c["telephone"] or None},
        "Niveau de confiance": {"select": {"name": c["niveau"]} if c.get("niveau") else None},
        "Priorité": {"number": int(c["priorite"]) if c.get("priorite") else None},
        "Adresse": {"select": {"name": c["statut"]}}, "Relation": {"select": {"name": c["relation"]}},
        "Premier échange": {"date": {"start": c["premier"]}}, "Dernier échange": {"date": {"start": c["dernier"]}},
        "Mails envoyés": {"number": int(c["envoyes"])}, "Mails reçus": {"number": int(c["recus"])},
        "Dernier sujet": text(c["sujet"]), "Source": {"select": {"name": c["source"]}}, "Cité par": text(c["cite_par"]),
    }
    return props


def company_properties(c: Dict[str, str]) -> Dict[str, Any]:
    return {
        "Entreprise": {"title": [{"text": {"content": c["entreprise"] or c["domaine"]}}]}, "Domaine": text(c["domaine"]),
        "Format d'adresse": {"select": {"name": c["format"]} if c["format"] else None},
        "Confiance": {"select": {"name": c["confiance"]}}, "Exemples": text(c["exemples"]),
        "Contacts": {"number": int(c["contacts"])}, "Adresses génériques": text(c["generiques"]),
        "Adresses invalides": text(c["invalides"]),
    }


def page_id_from(value: str) -> str:
    match = re.search(r"([0-9a-f]{32})", value.replace("-", ""))
    if not match:
        raise SystemExit(f"Identifiant de page Notion introuvable dans : {value}")
    raw = match.group(1)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def create_database(token: str, parent: str, title: str, props: Dict[str, Any]) -> str:
    body = {"parent": {"type": "page_id", "page_id": parent}, "title": [{"text": {"content": title}}], "properties": props}
    return pn.api("POST", f"{API}/databases", token, body)["id"]


def existing_rows(token: str, db_id: str, key: str, kind: str) -> Dict[str, str]:
    """Clé (email ou domaine) -> id de page, pour mettre à jour au lieu de dupliquer."""
    rows: Dict[str, str] = {}
    for page in pn.fetch_all_pages(token, db_id):
        prop = page["properties"].get(key, {})
        value = prop.get("email") if kind == "email" else pn.prop_text(page["properties"], key)
        if value:
            rows[value.lower()] = page["id"]
    return rows


def upsert(token: str, db_id: str, rows: List[Any], known: Dict[str, str]) -> int:
    for key_value, props in rows:
        page = known.get(key_value)
        if page:
            pn.api("PATCH", f"{API}/pages/{page}", token, {"properties": props})
        else:
            pn.api("POST", f"{API}/pages", token, {"parent": {"database_id": db_id}, "properties": props})
        time.sleep(PAUSE_S)
    return len(rows)


def load_ids(parent: Optional[str], token: str) -> Dict[str, str]:
    ids: Dict[str, str] = json.load(open(IDS_PATH, encoding="utf-8")) if os.path.exists(IDS_PATH) else {}
    if not ids:
        if not parent:
            raise SystemExit("Première fois : indiquez --page <URL de la page partagée avec l'intégration>.")
        page = page_id_from(parent)
        ids = {"page": page,
               "contacts": create_database(token, page, "Contacts", CONTACT_PROPS),
               "entreprises": create_database(token, page, "Entreprises et formats d'adresse", COMPANY_PROPS)}
        with open(IDS_PATH, "w", encoding="utf-8") as f:
            json.dump(ids, f, indent=1)
    else:
        # Bases créées avant l'ajout d'une colonne (ex. « Niveau de confiance », 2026-10-06) : Notion ajoute les
        # propriétés manquantes et laisse les autres telles quelles.
        pn.api("PATCH", f"{API}/databases/{ids['contacts']}", token, {"properties": CONTACT_PROPS})
        pn.api("PATCH", f"{API}/databases/{ids['entreprises']}", token, {"properties": COMPANY_PROPS})
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(description="Envoie le réseau de contacts dans Notion.")
    ap.add_argument("--page", help="URL ou id de la page Notion partagée avec l'intégration (première fois).")
    args = ap.parse_args()
    token = pn.get_token()
    ids = load_ids(args.page, token)
    with open(NETWORK_PATH, encoding="utf-8") as f:
        network = json.load(f)
    known = existing_rows(token, ids["contacts"], "Email", "email")
    n = upsert(token, ids["contacts"], [(c["email"], contact_properties(c)) for c in network["contacts"]], known)
    known = existing_rows(token, ids["entreprises"], "Domaine", "text")
    m = upsert(token, ids["entreprises"], [(c["domaine"], company_properties(c)) for c in network["entreprises"]], known)
    print(f"Notion à jour : {n} contacts, {m} entreprises.")


if __name__ == "__main__":
    main()
