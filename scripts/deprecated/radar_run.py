#!/usr/bin/env python3
"""DÉPRÉCIÉ le 2026-09-07 (décision M0, docs/plans/2026-09-07-plan-amelioration.md) — non
exécuté, conservé pour référence uniquement, ne pas réintégrer dans scripts/.

Ce script écrivait dans state/pending-notion-upsert.json en écrasant le fichier (offres
neuves du run uniquement), alors que scripts/scrape_ats_api.py (le script réellement
branché sur `hunt.py scan` et couvert par tests/test_ats_connectors.py) FUSIONNE au lieu
d'écraser. Les deux en alternance auraient effacé silencieusement des offres en attente.
Aucune tâche planifiée active ne l'appelait (vérifié via CronList et config/radar-routine-
prompt.md), et il n'était référencé ni dans README.md ni AGENTS.md. Ses améliorations de
filtrage jugées sûres (FUNCTION_EXCLUDE, FOREIGN_LANG, liste de villes élargie) ont été
fusionnées dans scrape_ats_api.py ; celles jugées trop risquées pour la couverture des
offres (contract_type() qui exclut une offre sans mot-clé stage/alternance explicite dans
le titre, cassait test_parse_ashby) n'ont volontairement PAS été reprises.

--- Docstring d'origine ci-dessous ---

Orchestrateur du Radar quotidien (détection seule, ne postule à rien).

Balaye les API publiques ATS (Greenhouse / Lever / Ashby) des entreprises seed
(config/companies.yaml), filtre strictement les offres stage|alternance en Data/IA,
déduplique contre state/seen.json (clé = entreprise|poste|lieu, minuscule sans accents),
score chaque offre neuve /100 + bonus d'autonomie, puis écrit dans
state/pending-notion-upsert.json et met à jour seen.json.

Sources ATS directes = candidature autonome (sans captcha/login) → priorité.

Usage:
  python scripts/radar_run.py [--dry-run] [--max-age-days N] [--seuil N]
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------ helpers

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    """minuscule, sans accents, espaces normalisés."""
    return re.sub(r"\s+", " ", strip_accents(str(s or "")).lower()).strip()


def city_of(loc: str) -> str:
    """'Paris, France' / 'Paris (75)' -> 'paris' (segment ville, normalisé)."""
    c = str(loc or "").split(",")[0]
    c = c.split("(")[0]
    return norm(c)


def dedup_key(entreprise: str, poste: str, lieu: str) -> str:
    return f"{norm(entreprise)}|{norm(poste)}|{city_of(lieu)}"


def fetch_json(url: str, timeout: int = 15) -> Optional[Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    return None


def normalize_date(val: Any) -> Tuple[str, int]:
    today = date.today()
    if not val:
        return today.isoformat(), 0
    try:
        if isinstance(val, (int, float)):
            ts = val / 1000.0 if val > 1e11 else float(val)
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            return d.isoformat(), max(0, (today - d).days)
        sv = str(val).strip()
        if sv.isdigit():
            n = int(sv)
            ts = n / 1000.0 if n > 1e11 else float(n)
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            return d.isoformat(), max(0, (today - d).days)
        if "T" in sv or "-" in sv:
            cl = sv.split("T")[0]
            if len(cl) == 10:
                d = datetime.strptime(cl, "%Y-%m-%d").date()
                return d.isoformat(), max(0, (today - d).days)
        if "/" in sv:
            p = sv.split("/")
            if len(p) == 3:
                d = datetime.strptime(sv, "%d/%m/%Y").date()
                return d.isoformat(), max(0, (today - d).days)
    except Exception:
        pass
    return today.isoformat(), 0


def html_to_text(s: str, limit: int = 600) -> str:
    txt = re.sub(r"<[^>]+>", " ", html.unescape(str(s or "")))
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:limit]


# ------------------------------------------------------------------ filtres

def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


# Frontières de mot pour éviter les faux positifs (intern -> internal, ml -> html...).
STAGE_RE = r"\b(stage|stagiaire|intern|internship|trainee|praktikum)\b|fin d'etudes"
ALT_RE = (r"\b(alternance|alternant|alternante|apprentissage|apprenti|apprentie|"
          r"apprenticeship|professionnalisation)\b|working student|contrat pro")

# Rôles data/IA affirmés dans le TITRE (signal fort).
STRONG_DATA = ["data scientist", "data engineer", "data analyst", "machine learning",
               "deep learning", "data science", "ml engineer", "mlops",
               "research engineer", "computer vision", "nlp", "llm", "genai",
               "gen ai", "generative ai", "ia generative", "intelligence artificielle",
               "ai engineer", "ai researcher", "applied scientist", "analytics engineer",
               "data & ai", "data/ai", "ai/ml", "ml/ai", "data & analytics",
               "data analytics", "data & ia", "artificial intelligence"]
# Signaux faibles/ambigus (à valider par absence de fonction non-data).
WEAK_DATA_RE = r"\b(ai|ia|ml|bi)\b|analytics|big data|\bdata\b"
# Fonctions clairement hors périmètre data/IA.
FUNCTION_EXCLUDE = ["finance", "financial", "audit", "compliance", "legal", "juriste",
                    "juridique", "rgpd", "dpo", "sales", "marketing", "communication",
                    "ressources humaines", "recruit", "talent", "asset", "stock",
                    "procurement", "supply chain", "accounting", "comptab", "fiscal",
                    " tax", "payroll", "paie", "product manager", "project manager",
                    "program manager", "ux ", "ui ", "growth", "sourcing", " sdr",
                    " bdr", "business develop", "partnership", "customer success",
                    "account manager", "operations manager", "office manager",
                    "designer", "consultant seo", "brand", "content"]
# Langues étrangères requises (hors FR/EN) -> mismatch.
FOREIGN_LANG = ["spanish speaker", "german speaker", "italian speaker", "dutch speaker",
                "portuguese speaker", "hispanohablante", "deutschsprachig"]

FR_LOC = ["paris", "ile-de-france", "idf", "france", "remote", "teletravail",
          "boulogne", "courbevoie", "levallois", "nanterre", "saint-denis", "issy",
          "montrouge", "puteaux", "clichy", "neuilly", "lyon", "nantes", "bordeaux",
          "toulouse", "rennes", "lille", "marseille", "grenoble", "sophia", "meudon",
          "massy", "charenton", "villejuif", "villeurbanne", "bois-colombes",
          "rueil", "argenteuil", "strasbourg", "nice", "montpellier"]

IDF_LOC = ["paris", "ile-de-france", "idf", "boulogne", "courbevoie", "levallois",
           "nanterre", "saint-denis", "issy", "montrouge", "puteaux", "clichy",
           "neuilly", "meudon", "massy", "charenton", "villejuif", "rueil",
           "argenteuil", "bois-colombes"]


def contract_type(title: str) -> Optional[str]:
    t = norm(title)
    if _has(STAGE_RE, t):
        return "stage"
    if _has(ALT_RE, t):
        return "alternance"
    return None


def is_data_domain(title: str, desc: str = "") -> bool:
    """Périmètre data/IA jugé sur le TITRE : rôle data affirmé, ou signal faible
    sans fonction métier hors-data. La description ne sert jamais à INCLURE
    (toute annonce mentionne 'AI'/'data')."""
    t = norm(title)
    if any(k in t for k in STRONG_DATA):
        return True
    if _has(WEAK_DATA_RE, t) and not any(f in t for f in FUNCTION_EXCLUDE):
        return True
    return False


def requires_foreign_lang(title: str, desc: str = "") -> bool:
    hay = f"{norm(title)} {norm(desc)}"
    return any(k in hay for k in FOREIGN_LANG)


def is_france(loc: str) -> bool:
    c = city_of(loc)
    if not c:
        return True  # localisation absente : on ne rejette pas (souvent poste FR)
    return any(k in norm(loc) for k in FR_LOC)


# ------------------------------------------------------------------ scoring

def score_offer(o: Dict[str, Any]) -> int:
    t = norm(o.get("poste", ""))
    hay = f"{t} {norm(o.get('description', ''))}"
    score = 45

    strong = ["genai", "ia generative", "generative ai", "llm", "rag", "nlp",
              "deep learning", "computer vision"]
    core = ["data scientist", "machine learning", "ml engineer", "data engineer",
            "data analyst", "research engineer"]
    tools = ["python", " sql", " bi ", "business intelligence", "analytics",
             "big data", "spark", "pytorch", "tensorflow", "power bi", "powerbi",
             "dataviz", "mlops"]
    dom = 0
    if any(k in hay for k in strong):
        dom += 20
    if any(k in t for k in core):
        dom += 14
    elif any(k in hay for k in core):
        dom += 8
    if any(k in hay for k in tools):
        dom += 8
    score += min(dom, 34)

    if o.get("type") in ("stage", "alternance"):
        score += 10
    if any(k in t for k in ["stage", "stagiaire", "intern", "alternance", "alternant",
                            "apprenti", "junior", "graduate", "debutant"]):
        score += 8
    if any(k in t for k in ["senior", "lead", "principal", "staff", "confirme",
                            "experimente"]):
        score -= 20

    city = norm(o.get("lieu", ""))
    if any(k in city for k in IDF_LOC):
        score += 10
    elif any(k in city for k in ["france", "remote", "teletravail", "lyon", "nantes",
                                 "bordeaux", "toulouse", "rennes", "lille", "marseille",
                                 "grenoble", "sophia"]):
        score += 7
    else:
        score += 3

    score += 4  # langue FR/EN OK

    age = o.get("age_jours", 0)
    if age <= 1:
        score += 8
    elif age <= 7:
        score += 6
    elif age <= 14:
        score += 3
    elif age > 30:
        score -= 6

    return max(20, min(92, score))


# ------------------------------------------------------------------ ATS parsers

def parse_greenhouse(slug: str, name: str) -> List[Dict[str, Any]]:
    data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not isinstance(data, dict):
        return []
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        loc = (j.get("location") or {}).get("name", "")
        ctype = contract_type(title)
        if not ctype:
            continue
        desc = html_to_text(j.get("content", ""))
        if not is_data_domain(title, desc):
            continue
        if not is_france(loc):
            continue
        diso, age = normalize_date(j.get("updated_at") or j.get("created_at"))
        out.append(_mk(name, title, ctype, j.get("absolute_url", ""), "Greenhouse",
                       "greenhouse", loc, desc, diso, age))
    return out


def parse_lever(slug: str, name: str) -> List[Dict[str, Any]]:
    data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(data, list):
        return []
    out = []
    for j in data:
        title = j.get("text", "")
        loc = (j.get("categories") or {}).get("location", "")
        ctype = contract_type(title)
        if not ctype:
            continue
        desc = html_to_text(j.get("descriptionPlain") or j.get("description", ""))
        if not is_data_domain(title, desc):
            continue
        if not is_france(loc):
            continue
        diso, age = normalize_date(j.get("createdAt"))
        out.append(_mk(name, title, ctype, j.get("hostedUrl", ""), "Lever",
                       "lever", loc, desc, diso, age))
    return out


def parse_ashby(slug: str, name: str) -> List[Dict[str, Any]]:
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not isinstance(data, dict):
        return []
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        loc = j.get("location", "") or ""
        ctype = contract_type(title)
        if not ctype:
            continue
        desc = html_to_text(j.get("descriptionPlain") or "")
        if not is_data_domain(title, desc):
            continue
        if not is_france(str(loc)):
            continue
        diso, age = normalize_date(j.get("publishedAt") or j.get("updatedAt"))
        out.append(_mk(name, title, ctype, j.get("jobUrl", ""), "Ashby",
                       "ashby", str(loc), desc, diso, age))
    return out


def _mk(entreprise, poste, ctype, lien, source, ats, lieu, desc, diso, age):
    return {
        "entreprise": entreprise, "poste": poste, "type": ctype, "lien": lien,
        "source": source, "ats": ats, "lieu": lieu or "Paris, France",
        "description": desc, "contact_recruteur": "", "date_publication": diso,
        "age_jours": age,
    }


# ------------------------------------------------------------------ main

AUTONOMIE_DEFAULT = {"teamtailor": "auto", "greenhouse": "auto", "ashby": "auto",
                     "tally": "auto", "lever": "captcha", "welcometothejungle": "login",
                     "linkedin": "login", "indeed": "login"}
BONUS_DEFAULT = {"auto": 8, "captcha": 2, "login": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-age-days", type=int, default=None)
    ap.add_argument("--seuil", type=int, default=None)
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config", "search-profiles.yaml"), encoding="utf-8") as f:
        prof = yaml.safe_load(f) or {}
    max_age = args.max_age_days if args.max_age_days is not None else int(prof.get("max_age_jours", 30))
    seuil = args.seuil if args.seuil is not None else int(prof.get("seuil_score", 60))
    autonomie_ats = {**AUTONOMIE_DEFAULT, **(prof.get("autonomie_ats") or {})}
    bonus = {**BONUS_DEFAULT, **(prof.get("bonus_autonomie") or {})}

    with open(os.path.join(ROOT, "config", "companies.yaml"), encoding="utf-8") as f:
        comp = (yaml.safe_load(f) or {}).get("entreprises", [])

    seen_path = os.path.join(ROOT, "state", "seen.json")
    seen = {"cles": []}
    if os.path.isfile(seen_path):
        with open(seen_path, encoding="utf-8") as f:
            seen = json.load(f)
    seen_keys: Set[str] = set(seen.get("cles", []))

    # 1) Balayage ATS directs
    raw: List[Dict[str, Any]] = []
    stats_src = {"greenhouse": 0, "lever": 0, "ashby": 0}
    errors: List[str] = []
    for c in comp:
        name = c.get("nom", "?")
        ats = (c.get("ats") or "").lower()
        url = c.get("careers_url", "")
        slug = url.rstrip("/").split("/")[-1]
        try:
            if ats == "greenhouse" or "greenhouse.io" in url:
                got = parse_greenhouse(slug, name); stats_src["greenhouse"] += len(got); raw += got
            elif ats == "lever" or "lever.co" in url:
                got = parse_lever(slug, name); stats_src["lever"] += len(got); raw += got
            elif ats == "ashby" or "ashbyhq.com" in url:
                got = parse_ashby(slug, name); stats_src["ashby"] += len(got); raw += got
        except Exception as e:
            errors.append(f"{name} ({ats}) : {e!r}")

    # 2a) Filtre langue étrangère requise (hors FR/EN)
    n_lang = sum(1 for o in raw if requires_foreign_lang(o["poste"], o.get("description", "")))
    raw = [o for o in raw if not requires_foreign_lang(o["poste"], o.get("description", ""))]

    # 2b) Filtre fraîcheur
    fresh = [o for o in raw if o.get("age_jours", 0) <= max_age]
    n_vieilles = len(raw) - len(fresh)

    # 3) Dédup vs seen.json
    neuves: List[Dict[str, Any]] = []
    n_deja = 0
    batch_keys: Set[str] = set()
    for o in fresh:
        k = dedup_key(o["entreprise"], o["poste"], o["lieu"])
        if k in seen_keys or k in batch_keys:
            n_deja += 1
            continue
        batch_keys.add(k)
        o["_cle"] = k
        neuves.append(o)

    # 4) Scoring + bonus autonomie + statut
    for o in neuves:
        base = score_offer(o)
        auton = autonomie_ats.get(o["ats"], "login")
        o["autonomie"] = auton
        o["score"] = min(100, base + bonus.get(auton, 0))
        o["statut"] = "À traiter" if o["score"] >= seuil else "Écartée"
        o["notes_matching"] = (f"ATS {o['source']} direct ({o['entreprise']}) | "
                               f"pub {o['date_publication']} ({o['age_jours']}j) | "
                               f"autonomie={auton}")

    neuves.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "date": date.today().isoformat(),
        "vus": len(raw),
        "stats_src": stats_src,
        "langue_ecartees": n_lang,
        "vieilles_ecartees": n_vieilles,
        "deja_vues": n_deja,
        "neuves": len(neuves),
        "retenues": sum(1 for o in neuves if o["statut"] == "À traiter"),
        "ecartees_score": sum(1 for o in neuves if o["statut"] == "Écartée"),
        "errors": errors,
        "offres": neuves,
    }

    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 5) Écriture pending-notion-upsert.json (offres neuves du run)
    pending_path = os.path.join(ROOT, "state", "pending-notion-upsert.json")
    fields = ["cle", "entreprise", "poste", "type", "lieu", "lien", "source", "ats",
              "description", "contact_recruteur", "score", "autonomie", "statut",
              "notes_matching", "date_publication"]
    offres_out = []
    for o in neuves:
        row = {k: o.get(k, "") for k in fields}
        row["cle"] = o["_cle"]
        offres_out.append(row)
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump({"offres": offres_out}, f, ensure_ascii=False, indent=2)

    # 6) MAJ seen.json (ajoute les nouvelles clés)
    seen["cles"] = list(seen.get("cles", [])) + [o["_cle"] for o in neuves]
    with open(seen_path, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: v for k, v in result.items() if k != "offres"},
                     ensure_ascii=False, indent=2))
    print(f"\nseen.json : {len(seen_keys)} -> {len(seen['cles'])} cles")
    print(f"pending-notion-upsert.json : {len(offres_out)} offres neuves ecrites")


if __name__ == "__main__":
    main()
