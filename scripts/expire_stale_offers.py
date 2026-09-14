#!/usr/bin/env python3
"""Écarte automatiquement les offres Notion « À traiter » devenues périmées.

Décision utilisateur (session du 2026-09-09), reprise ici :
  - Portée   : uniquement les pages au statut "À traiter" (celles déjà engagées —
    Postulé, Entretien, Offre reçue, Réponse reçue, Refusé — ne sont JAMAIS touchées,
    quel que soit leur âge, pour ne pas casser le suivi des relances).
  - Seuil    : 15 jours par défaut (configurable via --max-age-jours), calculé sur
    la date de création de la page Notion (`created_time` natif de l'API, aucune
    colonne « date de publication » n'existe dans le schéma — cf. offer_to_props()
    dans push_notion.py qui n'en écrit pas).
  - Action   : passe le Statut à "Écartée" (jamais de suppression ni d'archivage) —
    réversible en un clic, garde l'historique intact pour l'audit et les stats
    (analyze_response_rates.py, dashboard.py).
  - Cadence  : appelé depuis `hunt.py scan` (cf. cmd_scan) à chaque veille, donc pas
    besoin d'un cron séparé.

Ne modifie jamais une page dont le statut n'est pas exactement "À traiter". Si Notion
n'est pas configuré (kit fraîchement cloné, pas encore de config/notion.json), sort
silencieusement en succès : ce n'est pas une erreur, juste rien à faire.

Usage:
  python scripts/expire_stale_offers.py [--max-age-jours 15] [--dry-run]
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from logutil import log_error  # noqa: E402
import push_notion as pn  # noqa: E402

STATUT_CIBLE: str = "À traiter"
STATUT_ECARTE: str = "Écartée"
MAX_AGE_JOURS_DEFAUT: int = 15


def age_jours(created_time_iso: str) -> float:
    """created_time Notion est ISO8601 avec suffixe 'Z' (UTC) — non géré nativement
    par datetime.fromisoformat avant Python 3.11, d'où le remplacement explicite."""
    created = datetime.fromisoformat(created_time_iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400


def find_stale_pages(pages: List[Dict[str, Any]], max_age_jours: int) -> List[Dict[str, Any]]:
    stale: List[Dict[str, Any]] = []
    for pg in pages:
        props = pg.get("properties", {})
        if pn.prop_select(props, "Statut") != STATUT_CIBLE:
            continue
        age = age_jours(pg["created_time"])
        if age > max_age_jours:
            stale.append({
                "id": pg["id"],
                "entreprise": pn.prop_text(props, "Entreprise"),
                "poste": pn.prop_text(props, "Poste"),
                "lien": pn.prop_url(props, "Lien offre"),
                "age_jours": round(age, 1),
            })
    return stale


def write_log(stale: List[Dict[str, Any]], dry_run: bool) -> None:
    log_dir = os.path.join(ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"expire-stale-offers-{datetime.now().date().isoformat()}.log")
    prefix = "[dry-run] écarterait" if dry_run else "Écartée"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {len(stale)} offre(s) {prefix.lower()}\n")
        for o in stale:
            f.write(f"  - {prefix} : {o['entreprise']} - {o['poste']} ({o['age_jours']}j) {o['lien']}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Écarte les offres 'À traiter' périmées dans Notion")
    ap.add_argument("--max-age-jours", type=int, default=MAX_AGE_JOURS_DEFAUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        cfg = pn.load_cfg()
        db_id = pn.database_id_from_url(cfg["database_url"])
        token = pn.get_token()
        pages = pn.fetch_all_pages(token, db_id)
    except (SystemExit, FileNotFoundError):
        print("Notion non configuré — rien à écarter (lancez python scripts/init.py si besoin).")
        return 0
    except Exception as e:  # noqa: BLE001 — best-effort, ne doit jamais casser `hunt.py scan`
        log_error("expire_stale_offers: requête Notion", e)
        return 0

    stale = find_stale_pages(pages, args.max_age_jours)
    if not stale:
        print(f"Aucune offre 'À traiter' de plus de {args.max_age_jours} jours.")
        return 0

    for o in stale:
        tag = "[dry-run] " if args.dry_run else ""
        print(f"{tag}Écartée : {o['entreprise']} - {o['poste']} ({o['age_jours']}j)")
        if not args.dry_run:
            pn.api("PATCH", f"https://api.notion.com/v1/pages/{o['id']}", token,
                    {"properties": {"Statut": {"select": {"name": STATUT_ECARTE}}}})

    write_log(stale, args.dry_run)
    verbe = "écarterait" if args.dry_run else "écartée(s)"
    print(f"\n{len(stale)} offre(s) {verbe} (statut -> « {STATUT_ECARTE} »).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
