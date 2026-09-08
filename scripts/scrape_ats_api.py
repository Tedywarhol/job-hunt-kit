#!/usr/bin/env python3
"""Connecteurs d'API publics ATS (Greenhouse, Lever, Ashby) avec scoring de récence.

Récupère les offres en temps réel via les endpoints JSON officiels,
normalise les dates de publication vers la date ISO (ou aujourd'hui si absente),
et applique un bonus de récence pour prioriser les offres les plus fraîches.

Usage:
  python scripts/scrape_ats_api.py [--dry-run] [--max-age-days 30]
"""
import argparse
from datetime import date, datetime, timezone
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import yaml

from typing import Any, Dict, List, Optional, Set, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logutil import log_error
from netutil import with_retries

KEYWORDS_RELEVANCE: List[str] = [
    "data", "ia", "ai", "intelligence artificielle", "machine learning", "ml",
    "python", "deep learning", "nlp", "llm", "genai", "analytics", "bi",
    "big data", "computer vision", "ia générative", "informatique", "cloud",
    "business intelligence", "systèmes d'information", "logiciel", "software",
    "research engineer", "data engineer", "data scientist", "data analyst"
]

FR_LOC: List[str] = [
    "paris", "france", "remote", "télétravail", "île-de-france", "idf", "lyon", "bordeaux",
    "nantes", "rennes", "toulouse", "lille", "marseille", "grenoble", "sophia", "meudon",
    "massy", "charenton", "villejuif", "villeurbanne", "bois-colombes", "rueil", "argenteuil",
    "strasbourg", "nice", "montpellier", "boulogne", "courbevoie", "levallois", "nanterre",
    "saint-denis", "issy", "montrouge", "puteaux", "clichy", "neuilly",
]

CONTRACT_KEYWORDS: List[str] = [
    "alternance", "alternant", "alternante", "apprentissage", "apprenti", "apprentie",
    "contrat pro", "professionnalisation", "stage", "stagiaire", "intern", "internship",
    "working student", "trainee"
]

EXCLUDE_TITLES: List[str] = [
    "senior", "sr.", "staff", "lead", "principal", "director", "directeur", "directrice",
    "vp", "vice president", "head of", "head", "manager", "chief", "cdi", "permanent",
    "experienced", "sales executive", "account manager", "recruiter", "rh", "juriste", "legal"
]

# Fonctions métier clairement hors périmètre data/IA/tech (repris de scripts/radar_run.py,
# fusionné ici le 2026-09-07 — cf. décision M0 dans docs/plans/2026-09-07-plan-amelioration.md).
# Filtre additionnel : ne réduit jamais le domaine data/IA/tech déjà couvert par
# KEYWORDS_RELEVANCE, il élimine seulement les rôles métier non-tech qui contiendraient
# malgré tout un mot-clé de KEYWORDS_RELEVANCE par coïncidence (ex. "Data Privacy Officer").
FUNCTION_EXCLUDE: List[str] = [
    "finance", "financial", "audit", "compliance", "legal", "juriste", "juridique", "rgpd",
    "dpo", "sales", "marketing", "communication", "ressources humaines", "recruit", "talent",
    "asset", "stock", "procurement", "supply chain", "accounting", "comptab", "fiscal",
    " tax", "payroll", "paie", "product manager", "project manager", "program manager",
    "ux ", "ui ", "growth", "sourcing", " sdr", " bdr", "business develop", "partnership",
    "customer success", "account manager", "operations manager", "office manager",
    "designer", "consultant seo", "brand", "content",
]

# Offres exigeant une langue étrangère hors FR/EN -> mismatch avec le profil du candidat.
FOREIGN_LANG: List[str] = [
    "spanish speaker", "german speaker", "italian speaker", "dutch speaker",
    "portuguese speaker", "hispanohablante", "deutschsprachig",
]


def normalize_date(val: Any) -> Tuple[str, int]:
    """Convertit un timestamp, string ISO ou chaîne relative en (YYYY-MM-DD, age_en_jours)."""
    today = date.today()
    if not val:
        return today.isoformat(), 0

    try:
        # Cas 1: Entier / Float Unix timestamp (ms ou s)
        if isinstance(val, (int, float)):
            ts = val / 1000.0 if val > 1e11 else float(val)
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            age = max(0, (today - d).days)
            return d.isoformat(), age

        # Cas 2: Chaîne numérique
        str_val = str(val).strip()
        if str_val.isdigit():
            val_num = int(str_val)
            ts = val_num / 1000.0 if val_num > 1e11 else float(val_num)
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            return d.isoformat(), max(0, (today - d).days)

        # Cas 3: ISO 8601 (ex: "2026-08-28T14:30:00Z", "2026-09-01")
        if "T" in str_val or "-" in str_val:
            cleaned = str_val.split("T")[0]
            if len(cleaned) == 10:
                d = datetime.strptime(cleaned, "%Y-%m-%d").date()
                return d.isoformat(), max(0, (today - d).days)

        # Cas 4: Format français "DD/MM/YYYY"
        if "/" in str_val:
            parts = str_val.split("/")
            if len(parts) == 3:
                d = datetime.strptime(str_val, "%d/%m/%Y").date()
                return d.isoformat(), max(0, (today - d).days)
    except Exception:
        pass

    return today.isoformat(), 0


def calculate_recency_score(base_score: int, age_days: int) -> int:
    """Ajuste le score en favorisant fortement les offres très récentes."""
    bonus = 0
    if age_days <= 1:
        bonus = 15  # Offre du jour / hier
    elif age_days <= 7:
        bonus = 10  # Moins d'une semaine
    elif age_days <= 14:
        bonus = 5   # Moins de 2 semaines
    elif age_days > 45:
        bonus = -15 # Offre ancienne
    elif age_days > 30:
        bonus = -5

    return max(30, min(98, base_score + bonus))


def is_job_relevant(title: str, location: str = "", strict_alternance: bool = False) -> bool:
    """Filtre la pertinence d'une offre : domaine Data/IA, localisation, exclusion seniors,
    fonctions métier hors-scope (finance/legal/sales/RH/...) et langue étrangère requise."""
    t_lower = title.lower()
    loc_lower = location.lower()

    # 1. Exclusions seniors / direction / hors-cible
    if any(ex in t_lower for ex in EXCLUDE_TITLES):
        if not any(k in t_lower for k in ["alternance", "apprentissage", "stage", "intern"]):
            return False

    # 2. Exclusion des fonctions métier clairement hors data/IA/tech.
    if any(fx in t_lower for fx in FUNCTION_EXCLUDE):
        return False

    # 3. Exclusion des offres exigeant une langue étrangère hors FR/EN.
    if any(fl in t_lower for fl in FOREIGN_LANG):
        return False

    # 4. Filtre localisation (France / Paris / IDF / grandes villes / Remote FR)
    if loc_lower and not any(loc in loc_lower for loc in FR_LOC):
        return False

    # 5. Domaine : Data / IA / Informatique / Ingénierie
    is_domain = any(k in t_lower for k in KEYWORDS_RELEVANCE)
    if not is_domain:
        return False

    if strict_alternance:
        return any(ck in t_lower for ck in CONTRACT_KEYWORDS)

    return True


def fetch_json(url: str, timeout: int = 15) -> Optional[Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
    )

    def _do() -> Optional[Any]:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
        return None

    try:
        return with_retries(_do)
    except Exception as e:
        log_error(f"fetch_json({url})", e)
        return None



def parse_greenhouse(board_token: str, company_name: str) -> List[Dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    data = fetch_json(url)
    if not data or not isinstance(data, dict):
        return []

    jobs: List[Dict[str, Any]] = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        loc = (j.get("location") or {}).get("name", "")
        if not is_job_relevant(title, loc):
            continue

        raw_date = j.get("updated_at") or j.get("created_at")
        date_iso, age_days = normalize_date(raw_date)

        is_student = any(k in title.lower() for k in ["alternance", "stage", "intern", "apprenti"])
        base_score = 80 if is_student else 65
        final_score = calculate_recency_score(base_score, age_days)

        c_type = "stage" if "stage" in title.lower() or "intern" in title.lower() else "alternance"
        jobs.append({
            "entreprise": company_name,
            "poste": title,
            "type": c_type,
            "statut": "À traiter",
            "lien": j.get("absolute_url", ""),
            "source": "Greenhouse",
            "ats": "Greenhouse",
            "lieu": loc or "Paris, France",
            "date_publication": date_iso,
            "age_jours": age_days,
            "score": final_score,
            "notes_matching": f"API Greenhouse ({company_name}) | Publié le {date_iso} ({age_days}j)",
        })
    return jobs


def parse_lever(company: str, company_name: str) -> List[Dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = fetch_json(url)
    if not data or not isinstance(data, list):
        return []

    jobs: List[Dict[str, Any]] = []
    for j in data:
        title = j.get("text", "")
        cats = j.get("categories", {}) or {}
        loc = cats.get("location", "")
        if not is_job_relevant(title, loc):
            continue

        raw_date = j.get("createdAt")
        date_iso, age_days = normalize_date(raw_date)

        is_student = any(k in title.lower() for k in ["alternance", "stage", "intern", "apprenti"])
        base_score = 80 if is_student else 65
        final_score = calculate_recency_score(base_score, age_days)

        c_type = "stage" if "stage" in title.lower() or "intern" in title.lower() else "alternance"
        jobs.append({
            "entreprise": company_name,
            "poste": title,
            "type": c_type,
            "statut": "À traiter",
            "lien": j.get("hostedUrl", ""),
            "source": "Lever",
            "ats": "Lever",
            "lieu": loc or "Paris, France",
            "date_publication": date_iso,
            "age_jours": age_days,
            "score": final_score,
            "notes_matching": f"API Lever ({company_name}) | Publié le {date_iso} ({age_days}j)",
        })
    return jobs


def parse_ashby(org: str, company_name: str) -> List[Dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
    data = fetch_json(url)
    if not data or not isinstance(data, dict):
        return []

    jobs: List[Dict[str, Any]] = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        loc = j.get("location", "") or (j.get("secondaryLocations", [""])[0] if j.get("secondaryLocations") else "")
        if not is_job_relevant(title, str(loc)):
            continue

        raw_date = j.get("publishedAt") or j.get("updatedAt")
        date_iso, age_days = normalize_date(raw_date)

        is_student = any(k in title.lower() for k in ["alternance", "stage", "intern", "apprenti"])
        base_score = 80 if is_student else 65
        final_score = calculate_recency_score(base_score, age_days)

        c_type = "stage" if "stage" in title.lower() or "intern" in title.lower() else "alternance"
        jobs.append({
            "entreprise": company_name,
            "poste": title,
            "type": c_type,
            "statut": "À traiter",
            "lien": j.get("jobUrl", ""),
            "source": "Ashby",
            "ats": "Ashby",
            "lieu": str(loc) or "Paris, France",
            "date_publication": date_iso,
            "age_jours": age_days,
            "score": final_score,
            "notes_matching": f"API Ashby ({company_name}) | Publié le {date_iso} ({age_days}j)",
        })
    return jobs


def scan_target_companies(max_age_days: int = 45, verbose: bool = True) -> List[Dict[str, Any]]:
    cfg_path = os.path.join(ROOT, "config", "companies.yaml")
    if not os.path.isfile(cfg_path):
        return []

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    companies = cfg.get("entreprises", [])
    found_jobs: List[Dict[str, Any]] = []
    # N5 (UX, cf. plan d'amélioration) : ce scan interroge jusqu'à ~50 API une par une et
    # restait silencieux jusqu'au résultat final — plusieurs secondes sans aucun retour.
    # En terminal interactif, une seule ligne se met à jour (\r) ; en sortie redirigée
    # (log de routine planifiée), chaque ligne est conservée.
    interactive = verbose and sys.stdout.isatty()

    for i, comp in enumerate(companies, 1):
        name = comp.get("nom", "Inconnu")
        ats = comp.get("ats", "").lower()
        url = comp.get("careers_url", "")
        slug = url.rstrip("/").split("/")[-1]

        if verbose:
            end = "\r" if interactive else "\n"
            print(f"  [{i}/{len(companies)}] {name}...{'':<20}", end=end, flush=True)

        if ats == "greenhouse" or "greenhouse.io" in url:
            found_jobs.extend(parse_greenhouse(slug, name))
        elif ats == "lever" or "lever.co" in url:
            found_jobs.extend(parse_lever(slug, name))
        elif ats == "ashby" or "ashbyhq.com" in url:
            found_jobs.extend(parse_ashby(slug, name))

    if interactive:
        print(" " * 60, end="\r")  # efface la dernière ligne de progression

    # Filtrer par fraîcheur (<= max_age_days)
    if max_age_days > 0:
        found_jobs = [j for j in found_jobs if j.get("age_jours", 0) <= max_age_days]

    # Tri par score décroissant et date de publication la plus récente
    found_jobs.sort(key=lambda x: (x.get("score", 0), x.get("date_publication", "")), reverse=True)
    return found_jobs


def update_pending_upsert(new_jobs: List[Dict[str, Any]], max_age_days: int = 45) -> int:
    pending_file = os.path.join(ROOT, "state", "pending-notion-upsert.json")
    os.makedirs(os.path.dirname(pending_file), exist_ok=True)

    current_jobs: List[Dict[str, Any]] = []
    if os.path.isfile(pending_file):
        try:
            with open(pending_file, "r", encoding="utf-8") as f:
                raw_jobs = json.load(f).get("offres", [])
                # Nettoyer les offres obsolètes existantes
                current_jobs = [
                    j for j in raw_jobs
                    if max_age_days <= 0 or normalize_date(j.get("date_publication"))[1] <= max_age_days
                ]
        except Exception as e:
            # Fichier illisible/corrompu : on ne l'écrase pas en silence, on le
            # sauvegarde à côté avant de repartir d'une liste vide (perte visible,
            # pas perte silencieuse — cf. audit 2026-09-07).
            backup = pending_file + ".corrupt"
            try:
                shutil.copyfile(pending_file, backup)
            except OSError:
                backup = None
            log_error(
                f"update_pending_upsert: {pending_file} illisible, reset à vide"
                + (f" (copie conservée: {backup})" if backup else ""),
                e,
            )
            current_jobs = []

    existing_urls: Set[str] = {j.get("lien") for j in current_jobs if j.get("lien")}
    added = 0

    for job in new_jobs:
        if job.get("lien") and job["lien"] not in existing_urls:
            current_jobs.append(job)
            existing_urls.add(job["lien"])
            added += 1

    current_jobs.sort(key=lambda x: (x.get("score", 0), x.get("date_publication", "")), reverse=True)

    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump({"offres": current_jobs}, f, ensure_ascii=False, indent=2)

    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape rapide des API publiques d'ATS avec tri par fraîcheur.")
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans sauvegarder")
    parser.add_argument("--max-age-days", type=int, default=45, help="Âge maximal des offres en jours (défaut: 45)")
    args = parser.parse_args()

    print(f"🔎 Analyse approfondie des API ATS d'entreprises (offres < {args.max_age_days} jours)...")
    jobs = scan_target_companies(max_age_days=args.max_age_days)

    print(f"\n✨ {len(jobs)} opportunité(s) Data/IA/Tech récentes détectée(s) :\n")
    for j in jobs:
        print(f"  • [{j['score']}/100] ({j['date_publication']}, il y a {j['age_jours']}j) [{j['source']}] {j['entreprise']} — {j['poste']}")

    if not args.dry_run and jobs:
        added = update_pending_upsert(jobs)
        print(f"\n📥 {added} nouvelle(s) offre(s) synchronisée(s) vers state/pending-notion-upsert.json.")


if __name__ == "__main__":
    main()
