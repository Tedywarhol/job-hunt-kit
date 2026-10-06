#!/usr/bin/env python3
"""Garde-fou avant tout envoi : ne pas recontacter une entreprise qui a déjà refusé.

Constat du 2026-10-06 : un envoi groupé a relancé cinq entreprises qui avaient déjà
répondu non (dont une deux fois).
Ce module tient une liste unique des refus, `state/refus.json`, régénérable à partir de :
  - Gmail : les messages reçus qui contiennent une formule de refus ;
  - Notion : les lignes au statut « Refusé » qui ont un contact recruteur.

Usage :
  python scripts/contact_guard.py --refresh                 # reconstruit la liste (Gmail + Notion)
  python scripts/contact_guard.py adresse@exemple.fr ...    # verdict pour chaque adresse
Code de sortie : 2 si une adresse est bloquée, 1 si seulement des avertissements, 0 sinon.
"""
import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import push_notion as pn
from create_gmail_draft import get_gmail_service
from logutil import log_error
from profile import load_personal

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFUS_PATH: str = os.path.join(ROOT, "state", "refus.json")
GMAIL_DAYS: int = 180
GMAIL_PAGE_SIZE: int = 100
GMAIL_PAUSE_S: float = 0.15
NOTION_REFUSED: str = "Refusé"
# Le refus d'une AUTRE personne de l'entreprise ne compte que s'il est récent : les équipes changent.
DOMAIN_WINDOW_DAYS: int = 60

# Formules d'un refus. Un accusé de réception (« nous avons bien reçu ») n'en fait pas partie.
REFUSAL_RE = re.compile(
    # « malheureusement » seul ne suffit pas (« je n'en ai malheureusement pris connaissance qu'à mon retour »).
    r"(malheureusement[^.!?]{0,80}?(?:poste|alternan|budget|recrut|candidature|ouvert|opportunit|perspective|\bnon\b)|"
    r"au regret|pas de (?:poste|budget|perspectives?|service)|aucun poste|"
    r"(?:a|ont) été pourvue?s?|sont pourvu|déjà pourvu|retenu une autre|pas été retenue?|n'a pas été retenue?|"
    r"ne prenons pas d'alternan|pas d'alternance|ne recrute pas|réponse négative|suite favorable|"
    r"unfortunately|not (?:good luck|move forward)|no budget)",
    re.I,
)
GMAIL_QUERY_WORDS: str = (
    '(malheureusement OR regret OR regrettons OR pourvu OR pourvue OR "pas de poste" OR "aucun poste" OR "pas d\'alternance" '
    'OR "ne recrute pas" OR "autre candidature" OR "suite favorable" OR unfortunately OR "pas de budget")'
)
# Domaines partagés par plusieurs entreprises : on ne compare que l'adresse exacte.
SHARED_DOMAINS = {
    "gmail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr", "yahoo.com", "yahoo.fr",
    "icloud.com", "live.fr", "orange.fr", "free.fr", "laposte.net", "sfr.fr",
    "talent-soft.com", "profils.org", "welcomekit.co", "candidates.welcomekit.co", "recruitmail.com",
    "teamtailor-mail.com", "smartrecruiters.com", "greenhouse.io", "lever.co", "ashbyhq.com",
    "workablemail.com", "jobs2web.com", "myworkday.com", "successfactors.com", "hellowork.com",
}


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower()


def is_shared_domain(domain: str) -> bool:
    return any(domain == shared or domain.endswith("." + shared) for shared in SHARED_DOMAINS)


def is_refusal(text: str) -> bool:
    return bool(REFUSAL_RE.search(html.unescape(text or "")))


def add_refusal(refusals: Dict[str, List[Dict[str, str]]], address: str, when: str, source: str, extrait: str) -> None:
    """Range un refus sous l'adresse exacte ; la recherche par domaine se fait au moment du contrôle."""
    address = address.strip().lower()
    if "@" not in address:
        return
    entries = refusals.setdefault(address, [])
    if not any(e["date"] == when and e["source"] == source for e in entries):
        entries.append({"date": when, "source": source, "extrait": html.unescape(extrait)[:160]})


def check(
    address: str, refusals: Dict[str, List[Dict[str, str]]], today: Optional[date] = None,
) -> Optional[Dict[str, str]]:
    """Verdict pour une adresse : None, ou {niveau: bloqué|attention, raison}."""
    address = address.strip().lower()
    since = ((today or date.today()) - timedelta(days=DOMAIN_WINDOW_DAYS)).isoformat()
    if address in refusals:
        last = sorted(refusals[address], key=lambda e: e["date"])[-1]
        return {"niveau": "bloqué", "raison": f"{address} a déjà refusé le {last['date']} : « {last['extrait']} »"}
    domain = domain_of(address)
    if is_shared_domain(domain):
        return None
    same_company = sorted(
        a for a in refusals if domain_of(a) == domain and any(e["date"] >= since for e in refusals[a])
    )
    if not same_company:
        return None
    who = same_company[0]
    last = sorted(refusals[who], key=lambda e: e["date"])[-1]
    return {"niveau": "attention", "raison": f"{who}, de la même entreprise, a refusé le {last['date']} : « {last['extrait']} »"}


def load_refusals(path: str = REFUS_PATH) -> Dict[str, List[Dict[str, str]]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return data.get("refus", {})


def save_refusals(refusals: Dict[str, List[Dict[str, str]]], path: str = REFUS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"genere_le": datetime.now().isoformat(timespec="seconds"), "refus": refusals}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def collect_from_gmail(service: Any, refusals: Dict[str, List[Dict[str, str]]], me: str) -> int:
    """Ajoute les refus reçus par mail. Une erreur d'API remonte : une liste incomplète ne doit pas passer pour complète."""
    query = f"{GMAIL_QUERY_WORDS} -from:{me} newer_than:{GMAIL_DAYS}d"
    found, token = 0, None
    while True:
        page = service.users().messages().list(userId="me", q=query, maxResults=GMAIL_PAGE_SIZE, pageToken=token).execute()
        for ref in page.get("messages", []):
            msg = service.users().messages().get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["From"]).execute()
            sender = next((h["value"] for h in msg["payload"]["headers"] if h["name"].lower() == "from"), "")
            match = re.search(r"[\w.+'-]+@[\w.-]+", sender)
            snippet = msg.get("snippet", "")
            if match and is_refusal(snippet):
                when = date.fromtimestamp(int(msg["internalDate"]) / 1000).isoformat()
                add_refusal(refusals, match.group(0), when, "gmail", snippet)
                found += 1
            time.sleep(GMAIL_PAUSE_S)
        token = page.get("nextPageToken")
        if not token:
            return found


def contact_of(props: Dict[str, Any], name: str) -> str:
    """La colonne « Contact recruteur » peut être de type email ou texte."""
    value = props.get(name, {}) or {}
    return value.get("email") or pn.prop_text(props, name)


def collect_from_notion(refusals: Dict[str, List[Dict[str, str]]]) -> int:
    """Ajoute les lignes Notion « Refusé » qui ont une adresse de contact."""
    cfg = pn.load_cfg()
    cols = cfg["colonnes"]
    pages = pn.fetch_all_pages(pn.get_token(), pn.database_id_from_url(cfg["database_url"]))
    found = 0
    for page in pages:
        props = page.get("properties", {})
        if pn.prop_select(props, cols["statut"]) != NOTION_REFUSED:
            continue
        contact = contact_of(props, cols["contact"])
        match = re.search(r"[\w.+'-]+@[\w.-]+", contact or "")
        if match:
            when = (pn.prop_date(props, cols["date_candidature"]) or page.get("last_edited_time", "")[:10])
            add_refusal(refusals, match.group(0), when, "notion", pn.prop_text(props, cols["titre"]))
            found += 1
    return found


def refresh() -> Dict[str, List[Dict[str, str]]]:
    refusals: Dict[str, List[Dict[str, str]]] = {}
    me = load_personal().get("email", "")
    n_gmail = collect_from_gmail(get_gmail_service(), refusals, me)
    try:
        n_notion = collect_from_notion(refusals)
    except (SystemExit, KeyError, OSError) as e:
        log_error("contact_guard: lecture Notion (la liste ne contient que Gmail)", e)
        n_notion = 0
    save_refusals(refusals)
    print(f"Liste des refus reconstruite : {len(refusals)} adresse(s) ({n_gmail} via Gmail, {n_notion} via Notion) -> {REFUS_PATH}")
    return refusals


def main() -> None:
    ap = argparse.ArgumentParser(description="Garde-fou : une adresse ou une entreprise a-t-elle déjà refusé ?")
    ap.add_argument("adresses", nargs="*", help="Adresses à vérifier avant un envoi.")
    ap.add_argument("--refresh", action="store_true", help="Reconstruit state/refus.json depuis Gmail et Notion.")
    args = ap.parse_args()

    refusals = refresh() if args.refresh else load_refusals()
    if not args.adresses:
        return
    if not refusals:
        print("Liste des refus vide : lancez d'abord --refresh.", file=sys.stderr)
        sys.exit(1)
    worst = 0
    for address in args.adresses:
        verdict = check(address, refusals)
        if verdict is None:
            print(f"OK         {address}")
            continue
        worst = max(worst, 2 if verdict["niveau"] == "bloqué" else 1)
        print(f"{verdict['niveau'].upper():10} {address} : {verdict['raison']}")
    sys.exit(worst)


if __name__ == "__main__":
    main()
