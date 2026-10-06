#!/usr/bin/env python3
"""Données du tableau de bord de l'interface graphique (ui-agent), en JSON sur la sortie standard.

L'interface ne recalcule rien : toute la logique métier (échéances de relance, niveaux de
confiance, statuts réels) reste ici, dans le même code que la console, et l'écran l'affiche.
Lecture seule : aucun envoi, aucune écriture.

Usage:
  python scripts/ui_data.py                # inclut le statut réel dans Notion si configuré
  python scripts/ui_data.py --sans-notion  # local uniquement (instantané)
  python scripts/ui_data.py --demo         # données fictives, pour essayer l'interface ou la photographier
"""
import argparse
from datetime import date, datetime, timedelta
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dashboard
from network_patterns import TRUST_LEVELS
from run_followups import DELAIS_JOURS, anchor_plus, load_outreach, next_step

ETAPES_CLOSES = ("Terminé", "Réponse reçue")
STATUTS_CONNUS = ("Brouillon créé", "Envoyé", "Réponse reçue", "Terminé")
NETWORK_PATH: str = os.path.join(ROOT, "state", "network.json")
REFUS_PATH: str = os.path.join(ROOT, "state", "refus.json")


def read_json(path: str) -> Any:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def followups(entries: List[Dict[str, Any]], today: date, horizon_jours: int = 3) -> List[Dict[str, Any]]:
    """Relances dues ou à venir sous `horizon_jours`. `jours` < 0 : en retard, 0 : aujourd'hui."""
    result: List[Dict[str, Any]] = []
    for e in entries:
        etape = str(e.get("etape") or "J+0")
        anchor = e.get("date_j0") or e.get("date_creation_brouillon")
        nxt = next_step(etape)
        if etape in ETAPES_CLOSES or not anchor or not nxt:
            continue
        echeance = anchor_plus(str(anchor), DELAIS_JOURS[nxt])
        jours = (datetime.strptime(echeance, "%Y-%m-%d").date() - today).days
        if jours > horizon_jours:
            continue
        result.append({
            "entreprise": e.get("entreprise", "?"), "poste": e.get("poste", "?"),
            "etape_suivante": nxt, "echeance": echeance, "jours": jours,
        })
    return sorted(result, key=lambda r: r["echeance"])


def statuts_locaux(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Statuts de state/outreach.json regroupés : le champ contient aussi des notes libres."""
    counts: Dict[str, int] = {}
    for e in entries:
        statut = str(e.get("statut") or "")
        label = next((s for s in STATUTS_CONNUS if statut.startswith(s)), "Suivi libre")
        counts[label] = counts.get(label, 0) + 1
    return counts


def network_summary(network: Optional[Dict[str, Any]], refus: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not network:
        return None
    contacts: List[Dict[str, Any]] = network.get("contacts", [])
    par_niveau = {label: 0 for label in TRUST_LEVELS.values()}
    for c in contacts:
        label = c.get("niveau")
        if label in par_niveau:
            par_niveau[label] += 1
    opportunites = [c for c in contacts if c.get("priorite") == "1"]
    return {
        "genere_le": network.get("genere_le"),
        "contacts": len(contacts),
        "entreprises": len(network.get("entreprises", [])),
        # Un state/network.json généré avant les niveaux n'en porte pas : l'écran propose de le reconstruire.
        "niveaux_calcules": sum(par_niveau.values()) > 0,
        "par_niveau": par_niveau,
        "opportunites": [{"nom": c.get("nom") or c.get("email"), "entreprise": c.get("entreprise", "")}
                         for c in opportunites[:12]],
        "refus": len((refus or {}).get("refus", {})),
    }


def top_offers(offers: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    ranked = sorted(offers, key=lambda o: int(o.get("score") or 0), reverse=True)
    return [{
        "entreprise": o.get("entreprise") or o.get("administration") or "?",
        "poste": o.get("poste") or o.get("titre") or "?",
        "score": int(o.get("score") or 0), "age_jours": o.get("age_jours", 0),
        "lieu": o.get("lieu", ""), "lien": o.get("lien", ""),
    } for o in ranked[:limit]]


def recent_dossiers(apps: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    """Les dossiers outputs/<slug> les plus récemment modifiés, avec la présence des PDF."""
    def mtime(slug: str) -> float:
        return os.path.getmtime(os.path.join(ROOT, "outputs", slug))

    recents = sorted(apps, key=lambda a: mtime(a["slug"]), reverse=True)[:limit]
    return [{
        "slug": a["slug"], "entreprise": a["entreprise"], "poste": a.get("poste", ""),
        "pdf": any(f.endswith(".pdf") for f in os.listdir(os.path.join(ROOT, "outputs", a["slug"]))),
    } for a in recents]


def notion_block(snap: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if snap is None:
        return None
    return {
        "total": snap["total"],
        "statuts": dict(snap["statuts"]),
        "relances_en_retard": snap["relances_en_retard"],
    }


def build_payload(with_notion: bool, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    entries = load_outreach()
    offers = dashboard.load_all_opportunities()
    apps = dashboard.get_application_folders()
    return {
        "genere_le": today.isoformat(),
        "relances": followups(entries, today),
        "statuts_locaux": statuts_locaux(entries),
        "notion": notion_block(dashboard.load_notion_snapshot()) if with_notion else None,
        "fraicheur": dashboard.compute_freshness_kpis(offers),
        "offres": {"en_attente": len(offers), "meilleures": top_offers(offers)},
        "dossiers": {"total": len(apps), "recents": recent_dossiers(apps)},
        "reseau": network_summary(read_json(NETWORK_PATH), read_json(REFUS_PATH)),
    }


def demo_payload(today: Optional[date] = None) -> Dict[str, Any]:
    """Données entièrement fictives : aucune lecture de state/, outputs/ ou Notion."""
    today = today or date.today()
    day = lambda offset: (today + timedelta(days=offset)).isoformat()  # noqa: E731
    relance = lambda ent, poste, etape, jours: {  # noqa: E731
        "entreprise": ent, "poste": poste, "etape_suivante": etape, "echeance": day(jours), "jours": jours}
    offre = lambda ent, poste, score, age, lieu: {  # noqa: E731
        "entreprise": ent, "poste": poste, "score": score, "age_jours": age, "lieu": lieu,
        "lien": "https://exemple.invalid/offre"}
    return {
        "genere_le": today.isoformat(),
        "relances": [
            relance("Acme Aero", "Data analyst alternance", "J+5", -4),
            relance("Nordlys Data", "Ingénieur data en alternance", "J+3", 0),
            relance("Studio Fictif", "Analyste BI", "J+3", 2),
        ],
        "statuts_locaux": {"Brouillon créé": 4, "Envoyé": 7, "Réponse reçue": 9},
        "notion": {
            "total": 62,
            "statuts": {"À traiter": 8, "Postulé": 14, "Entretien": 3, "Offre reçue": 1, "Réponse reçue": 6,
                        "Refusé": 9, "Écartée": 21},
            "relances_en_retard": [],
        },
        "fraicheur": {"today": 2, "week": 9, "month": 14, "older": 3},
        "offres": {"en_attente": 28, "meilleures": [
            offre("Exemplia", "Data scientist alternance", 94, 1, "Paris"),
            offre("Acme Aero", "Ingénieur IA en alternance", 91, 2, "Toulouse"),
            offre("Nordlys Data", "Data engineer alternance", 88, 0, "Lille"),
            offre("Conseil Exemple", "Consultant data junior", 82, 5, "Paris"),
        ]},
        "dossiers": {"total": 41, "recents": [
            {"slug": "exemplia-data-scientist", "entreprise": "Exemplia", "poste": "Data scientist", "pdf": True},
            {"slug": "acme-aero-ingenieur-ia", "entreprise": "Acme Aero", "poste": "Ingénieur IA", "pdf": True},
            {"slug": "nordlys-data-data-engineer", "entreprise": "Nordlys Data", "poste": "Data engineer", "pdf": False},
        ]},
        "reseau": {
            "genere_le": today.isoformat(), "contacts": 210, "entreprises": 96, "niveaux_calcules": True,
            "par_niveau": {"Opportunité": 6, "Échange": 14, "Réponse": 41, "Refus": 22, "Sans réponse": 127},
            "opportunites": [{"nom": "Laura Blanc", "entreprise": "Exemplia"},
                             {"nom": "Paul Valmont", "entreprise": "Conseil Exemple"},
                             {"nom": "Camille Roche", "entreprise": "Acme Aero"}],
            "refus": 31,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Données JSON du tableau de bord (lecture seule).")
    parser.add_argument("--sans-notion", action="store_true", help="Ne pas interroger Notion.")
    parser.add_argument("--demo", action="store_true", help="Données fictives, sans rien lire.")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    payload = demo_payload() if args.demo else build_payload(with_notion=not args.sans_notion)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
