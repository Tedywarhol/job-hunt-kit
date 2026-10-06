#!/usr/bin/env python3
"""Radar LinkedIn : logique déterministe pour le repérage d'offres Data/IA récentes et peu
postulées via mcp-server-linkedin.

Contrairement à scrape_ats_api.py (API HTTP publiques, appelables en subprocess), les outils
mcp__mcp-server-linkedin__* ne sont accessibles que depuis une session Claude Code (agent
linkedin-scout, cf. .claude/agents/linkedin-scout.md). Ce module ne contient donc QUE la
logique pure (parsing, scoring, dédup/écriture d'état) : l'agent appelle search_jobs puis
get_job_details, et passe le texte brut de chaque page à build_offer() ci-dessous.

Réutilise is_job_relevant/calculate_recency_score/update_pending_upsert de scrape_ats_api.py
(même filtre domaine/localisation, même fichier d'état state/pending-notion-upsert.json,
même pipeline push_notion.py en aval) plutôt que de dupliquer cette logique.
"""
import os
import re
import sys
from datetime import date
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_ats_api import calculate_recency_score, is_job_relevant, update_pending_upsert

RELATIVE_AGE_RE = re.compile(r"il y a (\d+)\s*(heure|jour|semaine|mois)s?", re.IGNORECASE)
# LinkedIn affiche le signal de concurrence sous deux formulations distinctes observées en
# conditions réelles : « X candidats » (offres promues/CDI) et « (Plus de) X personnes ont
# cliqué sur Postuler » (offres alternance/stage classiques - la formulation que l'utilisateur
# avait anticipée). Un seul motif couvre les deux plutôt que d'en privilégier une.
CANDIDATE_COUNT_RE = re.compile(
    r"(?:plus de\s+)?(\d+)\s*(?:personnes?\s+ont\s+cliqu[ée]\s+sur\s+postuler|candidats?)\b",
    re.IGNORECASE,
)
EARLY_APPLICANT_RE = re.compile(r"premiers?\s+candidats?", re.IGNORECASE)


def parse_relative_age_days(text: str) -> Optional[int]:
    """Convertit une mention « il y a X jour(s)/semaine(s)/mois/heure(s) » (texte LinkedIn)
    en âge entier en jours. Renvoie None si aucune mention trouvée (l'appelant décide du
    défaut à appliquer plutôt que d'en supposer un ici)."""
    m = RELATIVE_AGE_RE.search(text)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return {"heure": 0, "jour": n, "semaine": n * 7, "mois": n * 30}[unit]


def parse_competition_signal(text: str) -> Dict[str, Any]:
    """Extrait le signal de concurrence d'une page get_job_details : nombre de candidats
    affiché par LinkedIn, ou badge « soyez l'un des premiers candidats » sur les offres très
    peu postulées. Aucun des deux n'est garanti présent sur toutes les offres."""
    is_early = bool(EARLY_APPLICANT_RE.search(text))
    m = CANDIDATE_COUNT_RE.search(text)
    return {"applicant_count": int(m.group(1)) if m else None, "is_early_applicant": is_early}


def competition_bonus(applicant_count: Optional[int], is_early_applicant: bool) -> int:
    """Bonus de score favorisant les offres peu postulées (demande explicite : éviter la
    concurrence sur des offres déjà noyées sous les candidatures). Ne fait jamais chuter une
    offre autrement pertinente en dessous du plancher de calculate_recency_score."""
    if is_early_applicant:
        return 15
    if applicant_count is None:
        return 0
    if applicant_count <= 10:
        return 12
    if applicant_count <= 25:
        return 6
    if applicant_count <= 50:
        return 0
    return -10


def competition_note(applicant_count: Optional[int], is_early_applicant: bool) -> str:
    if is_early_applicant:
        return "l'un des premiers candidats"
    if applicant_count is not None:
        return f"{applicant_count} candidat(s)"
    return "candidatures inconnues"


def build_offer(job_id: str, title: str, company: str, location: str, detail_text: str) -> Optional[Dict[str, Any]]:
    """Construit une offre au format state/pending-notion-upsert.json à partir du texte de
    get_job_details (agent linkedin-scout). Renvoie None si l'offre est filtrée par
    is_job_relevant (même filtre domaine/localisation/seniorité que le radar ATS)."""
    if not is_job_relevant(title, location):
        return None

    age_days = parse_relative_age_days(detail_text)
    if age_days is None:
        age_days = 0
    date_iso = date.fromordinal(date.today().toordinal() - age_days).isoformat()

    signal = parse_competition_signal(detail_text)
    is_student = any(k in title.lower() for k in ["alternance", "stage", "intern", "apprenti"])
    base_score = 80 if is_student else 65
    score = calculate_recency_score(base_score, age_days)
    score = max(30, min(98, score + competition_bonus(signal["applicant_count"], signal["is_early_applicant"])))

    c_type = "stage" if "stage" in title.lower() or "intern" in title.lower() else "alternance"
    return {
        "entreprise": company,
        "poste": title,
        "type": c_type,
        "statut": "À traiter",
        "lien": f"https://www.linkedin.com/jobs/view/{job_id}/",
        "source": "LinkedIn",
        "lieu": location or "Île-de-France, France",
        "date_publication": date_iso,
        "age_jours": age_days,
        "score": score,
        "notes_matching": (
            f"LinkedIn | Publié il y a {age_days}j | "
            f"{competition_note(signal['applicant_count'], signal['is_early_applicant'])}"
        ),
    }


def save_linkedin_jobs(jobs: List[Optional[Dict[str, Any]]]) -> int:
    """Dédup + écrit dans state/pending-notion-upsert.json (même fichier et mécanisme que le
    radar ATS) : push_notion.py les traite ensuite sans distinction de source."""
    return update_pending_upsert([j for j in jobs if j is not None])
