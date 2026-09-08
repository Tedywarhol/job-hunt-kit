#!/usr/bin/env python3
"""Filtre les offres d'alternance (idéalement 24 mois), calcule un score de pertinence et prépare les contacts.

Note (audit 2026-09-07, M6) : ce barème (`score_pass_offer`, spécifique aux offres PASS
fonction publique — titre + description texte libre, durée de contrat) est volontairement
distinct de celui de l'agent `relevance-scorer` (offres génériques WTTJ/Indeed/ATS, avec
bonus d'autonomie selon l'ATS qui n'a pas de sens ici). Les deux réutilisent la même
fraîcheur (`calculate_recency_score`), mais leur base métier diffère par nature des
sources qu'ils scorent — ce n'est pas une incohérence à corriger, plutôt deux barèmes
adaptés chacun à sa source. Documenté ici pour éviter une future tentative d'unification
qui perdrait cette spécificité.
"""
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from scrape_ats_api import calculate_recency_score, normalize_date


def score_pass_offer(o: Dict[str, Any]) -> Tuple[int, List[str], bool, str, int]:
    titre = str(o.get("titre", "")).lower()
    desc = (str(o.get("description_poste", "")) + " " + str(o.get("profil_recherche", ""))).lower()
    duree = str(o.get("duree_contrat", "")).lower()

    is_24_mois = False
    if "24" in duree or "2 ans" in duree or "2ans" in duree or "24 mois" in duree or "24" in desc or "deux ans" in desc or "master" in desc:
        is_24_mois = True
    elif "12" in duree and "24" not in duree:
        is_24_mois = False
    else:
        is_24_mois = True

    score = 50
    notes: List[str] = []

    if any(k in titre for k in ["ia", "intelligence artificielle", "llm", "genai", "data scientist"]):
        score += 35
        notes.append("Match fort IA/LLM/Data Science")
    elif any(k in titre for k in ["data engineer", "data analyst", "données", "data", "statistiques"]):
        score += 25
        notes.append("Match Data Engineer/Analyst")
    elif any(k in titre for k in ["si", "système d'information", "transformation numérique", "développeur", "full stack", "cloud", "automatisation"]):
        score += 18
        notes.append("Match SI / Dev / Automatisation")
    elif any(k in titre for k in ["innovation", "numérique", "digital", "projet"]):
        score += 10
        notes.append("Match Numérique / Projets")

    if any(k in desc for k in ["python", "machine learning", "ia", "intelligence artificielle", "sql", "power bi", "dashboard", "n8n", "llm", "langchain"]):
        score += 10
        notes.append("Compétences techniques clés mentionnées")

    if is_24_mois:
        score += 5
        notes.append(f"Durée: {o.get('duree_contrat') or '24 mois / variable'}")

    raw_date = o.get("date_publication") or o.get("date_debut")
    date_iso, age_days = normalize_date(raw_date)
    final_score = calculate_recency_score(score, age_days)

    return final_score, notes, is_24_mois, date_iso, age_days


import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Filtrage et scoring des offres d'alternance PASS.")
    parser.add_argument("--max-age-days", type=int, default=30, help="Âge maximal des offres en jours (défaut: 30)")
    parser.add_argument("--all-ages", action="store_true", help="Conserver toutes les offres sans filtre d'âge")
    args = parser.parse_args()

    in_file: str = os.path.join(ROOT, "state", "pass_offers_enriched.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord enrich_pass_offers.py.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    alternance_offers: List[Dict[str, Any]] = []
    filtered_out_stale = 0

    for o in offers:
        t_contrat = str(o.get("type_contrat", "")).lower()
        titre = str(o.get("titre", "")).lower()
        is_alternance = "apprentissage" in t_contrat or "alternance" in t_contrat or "apprenti" in titre
        if not is_alternance:
            continue

        score, notes, _, date_pub, age_days = score_pass_offer(o)

        if not args.all_ages and args.max_age_days > 0 and age_days > args.max_age_days:
            filtered_out_stale += 1
            continue

        emails: List[str] = o.get("contact_emails", [])
        contact_str = emails[0] if emails else ""

        o_clean = {
            "entreprise": o.get("administration") or o.get("recruteur") or "Fonction Publique",
            "poste": o.get("titre"),
            "type": "alternance",
            "statut": "À traiter",
            "lien": o.get("lien"),
            "source": "PASS",
            "ats": "Autre",
            "lieu": o.get("localisation") or "Île-de-France",
            "score": score,
            "date_publication": date_pub,
            "age_jours": age_days,
            "contact_recruteur": contact_str,
            "notes_matching": " | ".join(notes) + f" (Réf: {o.get('numero_offre')} | Publié: {date_pub})",
            "numero_offre": o.get("numero_offre"),
            "date_debut": o.get("date_debut"),
            "duree_contrat": o.get("duree_contrat"),
            "raw_emails": emails,
        }
        alternance_offers.append(o_clean)

    # Tri par score décroissant et date la plus récente
    alternance_offers.sort(key=lambda x: (x["score"], x.get("date_publication", "")), reverse=True)

    print(f"Total offres alternance identifiées : {len(alternance_offers) + filtered_out_stale}")
    if filtered_out_stale > 0:
        print(f"🧹 Offres obsolètes nettoyées (> {args.max_age_days} jours) : {filtered_out_stale}")
    print(f"✨ Offres récentes conservées : {len(alternance_offers)}")

    out_alt = os.path.join(ROOT, "state", "pass_alternance_scored.json")
    os.makedirs(os.path.dirname(out_alt), exist_ok=True)
    with open(out_alt, "w", encoding="utf-8") as f:
        json.dump(alternance_offers, f, ensure_ascii=False, indent=2)

    print(f"\n--- Top {min(15, len(alternance_offers))} Offres Alternance Récentes (Data / IA / SI / 24 mois) ---")
    for o in alternance_offers[:15]:
        print(f"- [{o['score']}/100 | {o['age_jours']}j] {o['poste']} | {o['entreprise']} (Durée: {o.get('duree_contrat')}) -> {o['contact_recruteur']}")


if __name__ == "__main__":
    main()
