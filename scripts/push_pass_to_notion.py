#!/usr/bin/env python3
"""Pousse les offres d'alternance PASS vers la base Notion "Candidatures Data/IA"."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push_notion as pn

from typing import Any, Dict, List, Optional, Set

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_pass_notion_props(o: Dict[str, Any], url: str) -> Dict[str, Any]:
    notes_full = f"{o.get('notes_matching', '')} | Réf: {o.get('numero_offre', 'N/A')} | Durée: {o.get('duree_contrat', 'N/A')}"
    if o.get("raw_emails") and len(o.get("raw_emails", [])) > 1:
        notes_full += f" | Autres emails: {', '.join(o['raw_emails'][1:])}"

    props: Dict[str, Any] = {
        "Entreprise": {"title": [{"text": {"content": str(o.get("entreprise", "Fonction Publique"))[:100]}}]},
        "Poste": {"rich_text": [{"text": {"content": str(o.get("poste", ""))[:200]}}]},
        "Type": {"select": {"name": "Alternance"}},
        "Statut": {"select": {"name": "À traiter"}},
        "Lien offre": {"url": url},
        "Source": {"select": {"name": "Autre"}},
        "Lieu": {"rich_text": [{"text": {"content": str(o.get("lieu") or "Île-de-France")[:100]}}]},
        "Score": {"number": int(o.get("score", 70))},
        "Notes matching": {"rich_text": [{"text": {"content": notes_full[:1900]}}]},
    }

    contact_email = o.get("contact_recruteur")
    if contact_email and "@" in contact_email:
        props["Contact recruteur"] = {"email": contact_email.strip()}
    return props


def main() -> None:
    cfg = pn.load_cfg()
    db_id = pn.database_id_from_url(cfg["database_url"])
    token = pn.get_token()

    in_file = os.path.join(ROOT, "state", "pass_alternance_scored.json")
    if not os.path.isfile(in_file):
        print(f"Fichier manquant : {in_file}. Lancez d'abord le scraping PASS.")
        return

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    print(f"Chargement de {len(offers)} offres d'alternance PASS...")
    pages = pn.fetch_all_pages(token, db_id)
    existing: Set[str] = {pn.prop_url(pg.get("properties", {}), "Lien offre") for pg in pages} - {""}
    print(f"La base Notion contient actuellement {len(existing)} liens d'offres.")

    created, skipped, doublons_possibles = 0, 0, 0
    for o in offers:
        url = o.get("lien")
        if not url or url in existing:
            skipped += 1
            continue

        # N3 : signal de quasi-doublon (texte similaire, lien différent) — jamais un skip
        # automatique, juste une alerte à côté de la création (cf. plan d'amélioration).
        similar = pn.find_similar_existing(pages, o.get("entreprise", ""), o.get("poste", ""))
        if similar:
            doublons_possibles += 1
            _, ratio = similar
            print(f"  ⚠️  Quasi-doublon possible ({ratio:.0%} similaire) : {o.get('entreprise')} - {o.get('poste')}")

        props = build_pass_notion_props(o, url)
        try:
            pn.api("POST", "https://api.notion.com/v1/pages", token, {"parent": {"database_id": db_id}, "properties": props})
            created += 1
            existing.add(url)
            print(f"  + [{o.get('score')}/100] Ajouté : {o.get('entreprise')} - {o.get('poste')}")
        except Exception as e:
            print(f"  x Erreur sur {o.get('poste')}: {e}")

    print(f"\nTerminé : {created} offres ajoutées à Notion, {skipped} ignorées (déjà présentes), {doublons_possibles} quasi-doublon(s) signalé(s).")


if __name__ == "__main__":
    main()
