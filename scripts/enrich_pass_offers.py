#!/usr/bin/env python3
"""Enrichit les offres PASS avec les détails complets de chaque fiche."""
import concurrent.futures
import json
import os
import re
import time
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

from typing import Any, Dict, List, Optional, Set

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL: str = "https://www.pass.fonction-publique.gouv.fr"


def extract_field_after_label(text: str, label: str, stop_labels: List[str]) -> str:
    pos = text.find(label)
    if pos == -1:
        return ""
    start = pos + len(label)
    sub = text[start:].strip()
    earliest = len(sub)
    for sl in stop_labels:
        sp = sub.find(sl)
        if sp != -1 and sp < earliest:
            earliest = sp
    return sub[:earliest].strip()


def parse_offer_detail(url: str) -> Dict[str, Any]:
    try:
        page = Fetcher.get(url, stealthy_headers=True, timeout=25)
        if page.status != 200:
            return {"url": url, "error": f"HTTP {page.status}"}

        full_text = page.get_all_text()

        emails: List[str] = []
        for a in page.css("a"):
            href = a.attrib.get("href", "")
            if href.startswith("mailto:"):
                em = href.replace("mailto:", "").split("?")[0].strip()
                if em and "@" in em and em not in emails:
                    emails.append(em)

        if not emails:
            found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_text)
            for em in found:
                if not em.endswith((".png", ".jpg", ".css", ".js")) and em not in emails:
                    emails.append(em)

        h1_tags = page.css("h1")
        titre = h1_tags[0].get_all_text().strip() if h1_tags else ""

        type_contrat = ""
        if "Type de contrat" in full_text:
            idx = full_text.find("Type de contrat")
            chunk = full_text[idx:idx+200]
            if "Apprentissage" in chunk:
                type_contrat = "Apprentissage"
            elif "Stage" in chunk:
                type_contrat = "Stage"

        num_match = re.search(r'Numéro d\'offre\s*[\n\r\t:]*\s*([A-Z0-9-]+)', full_text, re.IGNORECASE)
        numero_offre = num_match.group(1).strip() if num_match else ""

        admin_match = re.search(r'Administration de rattachement\s*[\n\r\t:]*\s*([^\n]+)', full_text)
        admin = admin_match.group(1).strip() if admin_match else ""

        debut_match = re.search(r'Début du contrat\s*[\n\r\t:]*\s*([^\n]+)', full_text)
        debut = debut_match.group(1).strip() if debut_match else ""

        duree_match = re.search(r'Durée du contrat\s*[\n\r\t:]*\s*([^\n]+)', full_text)
        duree = duree_match.group(1).strip() if duree_match else ""

        loc_match = re.search(r'Localisation du poste\s*[\n\r\t:]*\s*([^\n]+(?:\n[^\n]+){1,4})', full_text)
        loc = loc_match.group(1).strip().replace("\n", ", ") if loc_match else ""

        desc_poste = extract_field_after_label(
            full_text,
            "Description du poste",
            ["Numéro d'offre", "Type de contrat", "Détails de l'offre", "Descriptif du profil recherché"]
        )

        desc_profil = extract_field_after_label(
            full_text,
            "Descriptif du profil recherché",
            ["Conditions particulières", "Informations complémentaires", "Commentaires", "Informations pratiques", "Contact"]
        )

        contact_text = extract_field_after_label(
            full_text,
            "Contact",
            ["Haut de page", "Liens utiles", "Sites associés"]
        )

        return {
            "titre": titre,
            "numero_offre": numero_offre,
            "type_contrat": type_contrat,
            "administration": admin,
            "date_debut": debut,
            "duree_contrat": duree,
            "localisation": loc,
            "contact_emails": emails,
            "contact_text": contact_text[:300] if contact_text else "",
            "description_poste": desc_poste[:1000] if desc_poste else "",
            "profil_recherche": desc_profil[:1000] if desc_profil else "",
            "full_text_len": len(full_text),
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def enrich_all() -> None:
    in_file: str = os.path.join(ROOT, "state", "pass_offers_list.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord scrape_pass.py.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    print(f"Enriching {len(offers)} offers...")
    enriched: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_offer = {executor.submit(parse_offer_detail, o["lien"]): o for o in offers}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_offer)):
            offer_base = future_to_offer[future]
            try:
                detail = future.result()
                combined = {**offer_base, **detail}
                enriched.append(combined)
                if (i + 1) % 15 == 0 or (i + 1) == len(offers):
                    print(f"Progress: {i + 1}/{len(offers)} offers enriched...")
            except Exception as exc:
                print(f"Error for {offer_base['lien']}: {exc}")
                enriched.append(offer_base)

    out_file: str = os.path.join(ROOT, "state", "pass_offers_enriched.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(enriched)} enriched offers to {out_file}")


if __name__ == "__main__":
    enrich_all()
