#!/usr/bin/env python3
"""Dashboard Analytique Console du Job-Hunt Kit.

Visualise en temps reel :
- L'entonnoir de conversion (Detectees -> A traiter -> Postulees)
- Les indicateurs de fraicheur temporelle (Offres du jour, < 7j, < 30j)
- Le suivi des dossiers de candidatures et relances
- Les opportunites prioritaires les plus recentes avec contacts directs

Usage:
  python scripts/dashboard.py
"""
from collections import Counter
from datetime import date, datetime
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from logutil import log_error
from profile import load_personal


def load_all_opportunities() -> List[Dict[str, Any]]:
    offers: List[Dict[str, Any]] = []
    seen_links = set()

    for fname in ["pass_alternance_scored.json", "pending-notion-upsert.json"]:
        path = os.path.join(ROOT, "state", fname)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    items = raw.get("offres", []) if isinstance(raw, dict) else raw
                    for item in items:
                        lien = item.get("lien")
                        if lien and lien not in seen_links:
                            seen_links.add(lien)
                            offers.append(item)
            except Exception as e:
                log_error(f"load_all_opportunities({fname})", e)
    return offers


def compute_freshness_kpis(offers: List[Dict[str, Any]]) -> Dict[str, int]:
    today = date.today()
    kpis = {"today": 0, "week": 0, "month": 0, "older": 0}

    for o in offers:
        age = o.get("age_jours")
        if age is None:
            raw_date = o.get("date_publication") or o.get("date_debut")
            if raw_date and len(str(raw_date)) == 10:
                try:
                    d = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
                    age = max(0, (today - d).days)
                except Exception:
                    age = 0
            else:
                age = 0

        if age <= 1:
            kpis["today"] += 1
        elif age <= 7:
            kpis["week"] += 1
        elif age <= 30:
            kpis["month"] += 1
        else:
            kpis["older"] += 1

    return kpis


def get_application_folders() -> List[Dict[str, Any]]:
    apps: List[Dict[str, Any]] = []
    today = date.today()
    for slug_dir in glob.glob(os.path.join(ROOT, "outputs", "*")):
        if not os.path.isdir(slug_dir):
            continue
        slug = os.path.basename(slug_dir)
        if slug in ["archives", "previews", "radar", ".git"]:
            continue
        lettre_vars = os.path.join(slug_dir, "lettre-vars.json")
        cv_vars = os.path.join(slug_dir, "cv-vars.json")

        app_info: Dict[str, Any] = {
            "slug": slug,
            # Repli si lettre-vars.json est absent : le slug complet prettifié est plus
            # fiable que son 1er segment seul (ex. "min-armees-..." -> "Min" à tort avant
            # ce correctif, cf. audit 2026-09-07 §3 — bug latent, pas observé sur les
            # dossiers réels car ils ont tous un lettre-vars.json, mais corrigé quand même).
            "entreprise": slug.replace("-", " ").title(),
            "date": today.isoformat(),
            "has_lettre": os.path.isfile(lettre_vars),
            "has_cv": os.path.isfile(cv_vars),
        }
        if os.path.isfile(lettre_vars):
            try:
                with open(lettre_vars, "r", encoding="utf-8") as f:
                    lv = json.load(f)
                    app_info["entreprise"] = lv.get("entreprise") or app_info["entreprise"]
                    app_info["poste"] = lv.get("poste") or ""
            except Exception as e:
                log_error(f"get_application_folders: lecture {lettre_vars}", e)
        apps.append(app_info)
    return apps


def render_follow_up_radar(apps: List[Dict[str, Any]]) -> str:
    if not apps:
        return "    (Aucune candidature active enregistree)"

    lines: List[str] = []
    lines.append("  +-------------------------------------------------------------+")
    lines.append(f"  | CANDIDATURES EN COURS ({len(apps)} dossiers prepares) :{'':<28}|")
    for app in apps[:6]:
        ent = str(app.get("entreprise", "Entreprise"))[:20]
        slug = str(app.get("slug", ""))[:32]
        lines.append(f"  |   * {ent:<20} -> outputs/{slug:<25}|")
    lines.append("  +-------------------------------------------------------------+")
    return "\n".join(lines)


def render_freshness_box(kpis: Dict[str, int]) -> str:
    return (
        f"  - Offres du jour / 24h  : {kpis['today']:>3}\n"
        f"  - Cette semaine (< 7j)  : {kpis['week']:>3}\n"
        f"  - Ce mois-ci (< 30j)    : {kpis['month']:>3}\n"
        f"  - Plus de 30 jours      : {kpis['older']:>3}"
    )


RELANCE_ETAPES_TERMINALES = ("Terminé", "Réponse reçue")


def load_notion_snapshot() -> Optional[Dict[str, Any]]:
    """Interroge Notion pour le statut RÉEL des candidatures (Postulé/Entretien/Refusé/...),
    contrairement à load_all_opportunities() qui ne voit que le stock local pré-candidature.
    Renvoie None si Notion n'est pas configuré — cas normal, pas une erreur (le dashboard
    reste utilisable sans Notion, juste avec un entonnoir moins complet)."""
    try:
        import push_notion as pn
    except Exception as e:
        log_error("load_notion_snapshot: import push_notion", e)
        return None

    try:
        cfg = pn.load_cfg()
        db_id = pn.database_id_from_url(cfg["database_url"])
        token = pn.get_token()
    except (SystemExit, FileNotFoundError):
        return None  # Notion non configuré : cas normal, pas une erreur à logger.
    except Exception as e:
        log_error("load_notion_snapshot: configuration Notion", e)
        return None

    try:
        pages = pn.fetch_all_pages(token, db_id)
    except Exception as e:
        log_error("load_notion_snapshot: requête Notion", e)
        return None

    today = date.today().isoformat()
    statuts: Counter = Counter()
    relances_en_retard: List[Dict[str, str]] = []
    for pg in pages:
        props = pg.get("properties", {})
        statut = pn.prop_select(props, "Statut") or "(sans statut)"
        statuts[statut] += 1

        etape = pn.prop_select(props, "Étape relance")
        date_prochaine = pn.prop_date(props, "Date prochaine relance")
        if etape and etape not in RELANCE_ETAPES_TERMINALES and date_prochaine and date_prochaine < today:
            relances_en_retard.append({
                "entreprise": pn.prop_text(props, "Entreprise"),
                "poste": pn.prop_text(props, "Poste"),
                "etape": etape,
                "date_prochaine": date_prochaine,
            })

    return {"total": len(pages), "statuts": statuts, "relances_en_retard": relances_en_retard}


ORDRE_STATUTS_AFFICHES: List[str] = [
    "À traiter", "Postulé", "Entretien", "Offre reçue", "Réponse reçue", "Refusé", "Écartée",
]


def render_notion_funnel(snap: Optional[Dict[str, Any]]) -> str:
    if snap is None:
        return "    (Notion non configuré ou injoignable — entonnoir ci-dessus limité au stock local)"
    statuts: Counter = snap["statuts"]
    lines = [f"  Total dans Notion : {snap['total']}"]
    for name in ORDRE_STATUTS_AFFICHES:
        if statuts.get(name):
            lines.append(f"    - {name:<14} : {statuts[name]}")
    autres = sum(v for k, v in statuts.items() if k not in ORDRE_STATUTS_AFFICHES)
    if autres:
        lines.append(f"    - (autre statut) : {autres}")
    return "\n".join(lines)


def render_relances_en_retard(snap: Optional[Dict[str, Any]]) -> str:
    if snap is None or not snap.get("relances_en_retard"):
        return "  Aucune relance en retard (ou Notion non configuré)."
    retard: List[Dict[str, str]] = snap["relances_en_retard"]
    lines = [f"  {len(retard)} relance(s) en retard :"]
    for r in retard[:10]:
        lines.append(f"    ! {r['entreprise']} / {r['poste']} -> {r['etape']} attendue le {r['date_prochaine']}")
    lines.append("  -> python scripts/run_followups.py --apply")
    return "\n".join(lines)


def render_top_fresh_offers(offers: List[Dict[str, Any]], limit: int = 5) -> str:
    today = date.today().isoformat()
    sorted_offers = sorted(
        offers,
        key=lambda x: (int(x.get("score") or 0), str(x.get("date_publication") or today)),
        reverse=True
    )
    lines: List[str] = []
    for i, o in enumerate(sorted_offers[:limit], 1):
        score = o.get("score", 70)
        titre = str(o.get("poste") or o.get("titre") or "Poste")[:45]
        admin = str(o.get("entreprise") or o.get("administration") or "Entreprise")[:24]
        date_pub = o.get("date_publication") or today
        age = o.get("age_jours", 0)
        contact = o.get("contact_recruteur") or "Formulaire direct"
        lines.append(
            f"    [{i}] Score: {score}/100 ({date_pub}, {age}j) - {titre}\n"
            f"        Entreprise : {admin} | Lieu : {o.get('lieu', 'France')[:30]} | Contact : {contact}"
        )
    return "\n".join(lines) if lines else "    (Aucune opportunite recente disponible)"


def main() -> None:
    p = load_personal()
    offers = load_all_opportunities()
    apps = get_application_folders()
    kpis = compute_freshness_kpis(offers)
    notion_snap = load_notion_snapshot()

    today_str = date.today().strftime("%d/%m/%Y")
    total_detected = len(offers) + len(apps)

    print("\n" + "=" * 67)
    print(f"TABLEAU DE BORD DE VEILLE & CANDIDATURES — {p.get('nom', 'Candidat').upper()}")
    print(f"Date : {today_str} | Statut : En recherche active")
    print("=" * 67)

    print("\nENTONNOIR DE RECHERCHE :")
    print(f"  +-------------------------------------------------------------+")
    print(f"  | Total Opportunites Detectees : {total_detected:<29}|")
    print(f"  | File d'Attente Active        : {len(offers):<29}|")
    print(f"  | Dossiers Prepares (Outputs)  : {len(apps):<29}|")
    print(f"  +-------------------------------------------------------------+")

    print("\nFRAICHEUR DES OFFRES :")
    print(render_freshness_box(kpis))

    print("\nSTATUT REEL DES CANDIDATURES (Notion) :")
    print(render_notion_funnel(notion_snap))

    print("\nRELANCES :")
    print(render_relances_en_retard(notion_snap))

    print("\nSUIVI DES DOSSIERS DE CANDIDATURE :")
    print(render_follow_up_radar(apps))

    print("\nTOP OPPORTUNITES RECENTES :")
    print(render_top_fresh_offers(offers, limit=5))

    print("\n" + "=" * 67 + "\n")


if __name__ == "__main__":
    main()
