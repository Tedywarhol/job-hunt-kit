#!/usr/bin/env python3
"""Réseau de contacts : tous les échanges depuis une date, les formats d'adresse par entreprise, et
la construction d'une adresse pour une personne repérée sur LinkedIn.

Usage :
  python scripts/network.py build [--depuis 2026-04-01]      # Gmail -> state/network.json + outputs/reseau/*.csv
  python scripts/network.py adresse <entreprise|domaine> <Prénom> <Nom>   # adresse probable + garde-fou des refus

Lecture seule sur Gmail. La base Notion est alimentée par scripts/network_notion.py.
"""
import argparse
import csv
import json
import os
import re
from datetime import date
from email.utils import getaddresses
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional, Pattern, Tuple

import contact_guard
import push_notion as pn
from gmail_reader import GmailReader
from network_lookup import NETWORK_PATH, guess, manual_opportunities
from profile import load_personal
from network_patterns import (
    address_status, is_generic, extract_phone, extract_title, names_from_local,
    signature_block, split_name, summarize_domains, TRUST_LEVELS, trust_level,
)

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR: str = os.path.join(ROOT, "outputs", "reseau")
CACHE_PATH: str = os.path.join(ROOT, "state", "network-gmail-cache.json")
FREE_MAIL = {"gmail.com", "hotmail.com", "hotmail.fr", "outlook.com", "outlook.fr", "yahoo.fr", "yahoo.com", "live.fr", "icloud.com"}
AUTOMATED = re.compile(
    r"(no-?reply|ne-?pas-?repondre|notification|mailer-daemon|postmaster|newsletter|alert|bounce|"
    r"linkedin\.com|indeed|hellowork|meteojob|welcometothejungle|jobteaser|profils\.org|talent-soft|"
    r"jobs2web|smartrecruiters|workday|successfactors|google\.com|github\.com|notion|uber|spotify|apple)",
    re.I,
)
JOB_WORDS = re.compile(r"(candidature|alternan|entretien|recrut|apprenti|stage|cv\b|poste|offre|profil|emploi)", re.I)
EMAIL_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,24}\b")
STRICT_JOB = re.compile(r"(candidature|alternan|entretien|recrut|apprenti|spontan)", re.I)
AUTO_REPLY = re.compile(r"(r[ée]ponse automatique|automatic reply|risposta automatica|out of office|absence|absent|auto-?reply|accus[ée] de r[ée]ception)", re.I)
PLACEHOLDER = re.compile(r"(pr[ée]nom|^nom[._]|[._]nom$|xxx|exemple)", re.I)  # « prénom.nom@entreprise.fr » donné comme modèle
STUDENT_DOMAIN = re.compile(r"(^|\.)(edu|etu|etud|student|students)\.", re.I)


def _personal() -> Dict[str, Any]:
    """Le bloc `personal` du profil, ou rien si le profil n'existe pas encore (machine fraîche, CI)."""
    try:
        return load_personal()
    except SystemExit:
        return {}


@lru_cache(maxsize=1)
def my_addresses() -> FrozenSet[str]:
    """Mes propres adresses (profil : `email` + `emails_secondaires`) : je ne suis jamais un contact."""
    personal = _personal()
    found = [personal.get("email", "")] + list(personal.get("emails_secondaires") or [])
    return frozenset(a.strip().lower() for a in found if a and a.strip())


@lru_cache(maxsize=1)
def mine_pattern() -> Pattern[str]:
    """Ma propre signature citée dans une réponse (mon nom, « étudiant ») n'est pas la fonction du contact."""
    personal = _personal()
    words = [re.escape(n.strip()) for n in (personal.get("prenom", ""), personal.get("nom_famille", "")) if n and len(n.strip()) > 1]
    return re.compile("(" + "|".join(words + [r"[ée]tudiant", r"[ée]l[èe]ve"]) + ")", re.I)


def keep(address: str, subject: str) -> bool:
    """Un contact professionnel : ni moi, ni un robot, ni un proche hors candidature."""
    address = address.lower()
    domain = address.rsplit("@", 1)[-1]
    if address in my_addresses() or AUTOMATED.search(address) or "=" in address.split("@")[0]:
        return False  # « = » : adresse relais d'un outil d'envoi (HubSpot...), pas une personne
    return domain not in FREE_MAIL or bool(JOB_WORDS.search(subject or ""))


def shareable(address: str) -> bool:
    """Un contact cité dans un mail : une personne nommée d'une entreprise, pas un candidat ni une boîte générique."""
    domain = address.rsplit("@", 1)[-1]
    return (keep(address, "") and domain not in FREE_MAIL and not STUDENT_DOMAIN.search(domain)
            and not is_generic(address) and not re.search(r"\.(png|jpe?g|gif)$", address.split("@")[0])
            and not PLACEHOLDER.search(address.split("@")[0]) and bool(names_from_local(address)[0]))


def touch(people: Dict[str, Dict[str, Any]], address: str, display: str, when: str, direction: str, subject: str) -> None:
    person = people.setdefault(address.lower(), {
        "email": address.lower(), "affichage": "", "envoyes": 0, "recus": 0, "premier": when, "dernier": when,
        "sujet": "", "telephone": "", "fonction": "", "source": "échange", "cite_par": "", "auto": 0, "sujets": [],
    })
    if display and len(display) > len(person["affichage"]):
        person["affichage"] = display
    if subject and subject not in person["sujets"]:
        person["sujets"].append(subject[:120])
    person["premier"], person["dernier"] = min(person["premier"], when), max(person["dernier"], when)
    person[{"sent": "envoyes", "auto": "auto"}.get(direction, "recus")] += 1
    if when >= person["dernier"]:
        person["sujet"] = subject[:120]


def collect_sent(reader: GmailReader, people: Dict[str, Dict[str, Any]], since: str) -> List[str]:
    threads = set()
    for ref in reader.ids(f"in:sent after:{since.replace('-', '/')}"):
        head = reader.headers(ref["id"])
        threads.add(head["thread"])
        for display, address in getaddresses([head.get("to", ""), head.get("cc", "")]):
            if address and keep(address, head.get("subject", "")):
                touch(people, address, display, head["date"], "sent", head.get("subject", ""))
    return sorted(threads)


def note_sender(people: Dict[str, Dict[str, Any]], latest: Dict[str, Tuple[str, str]],
                msg_id: str, head: Dict[str, Any]) -> None:
    display, address = getaddresses([head.get("from", "")])[0]
    if not address or not keep(address, head.get("subject", "")):
        return
    automatic = bool(AUTO_REPLY.search(head.get("subject", "")))
    touch(people, address, display, head["date"], "auto" if automatic else "received", head.get("subject", ""))
    if not automatic and head["date"] >= latest.get(address.lower(), ("", ""))[0]:
        latest[address.lower()] = (head["date"], msg_id)


def collect_received(reader: GmailReader, people: Dict[str, Dict[str, Any]], threads: List[str], since: str) -> Dict[str, str]:
    """Expéditeurs humains : tous les participants de mes fils, puis les mails de candidature reçus hors de ces fils."""
    latest: Dict[str, Tuple[str, str]] = {}
    for thread_id in threads:
        for head in reader.thread(thread_id):
            if head["date"] >= since:
                note_sender(people, latest, head["id"], head)
    query = (f"-in:sent after:{since.replace('-', '/')} -category:promotions -category:social "
             "(candidature OR alternance OR entretien OR recrutement OR apprentissage OR poste)")
    known = set(threads)
    for ref in reader.ids(query):
        head = reader.headers(ref["id"])
        if ref["threadId"] not in known and STRICT_JOB.search(head.get("subject", "")):
            note_sender(people, latest, ref["id"], head)
    return {address: msg_id for address, (_, msg_id) in latest.items()}


def collect_bounces(reader: GmailReader, since: str) -> List[str]:
    bounced = set()
    for ref in reader.ids(f"from:mailer-daemon after:{since.replace('-', '/')}"):
        for address in EMAIL_RE.findall(reader.body(ref["id"])):
            if address.lower() not in my_addresses() and not AUTOMATED.search(address):
                bounced.add(address.lower())
    return sorted(bounced)


def my_phone(phone: str) -> bool:
    """Le numéro lu est-il le mien (ma propre signature, citée dans la réponse) ?"""
    mine = re.sub(r"\D", "", _personal().get("telephone", ""))[-9:]
    return bool(mine) and re.sub(r"\D", "", phone).endswith(mine)


def enrich_from_signatures(reader: GmailReader, people: Dict[str, Dict[str, Any]], latest: Dict[str, str]) -> None:
    """Fonction et téléphone depuis la dernière signature ; adresses citées = contacts partagés."""
    for address, msg_id in latest.items():
        person = people[address]
        first, last = split_name(person["affichage"], address)
        body = reader.body(msg_id)
        block = signature_block(body, first, last)
        phone, title = extract_phone(block), extract_title(block)
        if phone and not my_phone(phone):
            person["telephone"] = person["telephone"] or phone
        if title and not mine_pattern().search(title):
            person["fonction"] = person["fonction"] or title
        own = re.split(r"\n\s*(?:Le .{5,120} a écrit|On .{5,120} wrote|De ?: |From: )", body)[0]
        for cited in EMAIL_RE.findall(own):
            cited = cited.lower().rstrip(".")
            if cited not in people and shareable(cited):
                people[cited] = {**people[address], "email": cited, "affichage": "", "envoyes": 0, "recus": 0,
                                 "telephone": "", "fonction": "", "source": "contact partagé", "cite_par": address}


def company_names() -> Tuple[Dict[str, str], Dict[str, str], set]:
    """Entreprise par adresse et par domaine, et domaines dont une candidature est au statut « Entretien », depuis le
    suivi Notion des candidatures."""
    cfg = pn.load_cfg()
    cols = cfg["colonnes"]
    by_email: Dict[str, str] = {}
    by_domain: Dict[str, str] = {}
    interviewing = set()
    for page in pn.fetch_all_pages(pn.get_token(), pn.database_id_from_url(cfg["database_url"])):
        props = page["properties"]
        name = re.sub(r"\s*\(.*?\)", "", pn.prop_text(props, cols["titre"])).strip()
        contact = (props.get(cols["contact"], {}) or {}).get("email") or pn.prop_text(props, cols["contact"])
        for address in EMAIL_RE.findall(contact or ""):
            by_email[address.lower()] = name
            by_domain.setdefault(address.lower().rsplit("@", 1)[-1], name)
            if pn.prop_select(props, cols["statut"]) == "Entretien":
                interviewing.add(address.lower().rsplit("@", 1)[-1])
    return by_email, by_domain, interviewing


def company_of(person: Dict[str, Any], by_email: Dict[str, str], by_domain: Dict[str, str]) -> str:
    domain = person["email"].rsplit("@", 1)[-1]
    paren = re.search(r"\(([^)]{3,60})\)", person["affichage"])
    if person["email"] in by_email:
        return by_email[person["email"]]
    if domain in by_domain:
        return by_domain[domain]
    if paren:
        return paren.group(1).title()
    return "" if domain in FREE_MAIL else domain.split(".")[-2].replace("-", " ").title()


def relation_of(person: Dict[str, Any], verdict: Optional[Dict[str, str]]) -> str:
    if verdict and verdict["niveau"] == "bloqué":
        return "a refusé"
    if person["recus"]:
        return "a répondu"
    return "réponse automatique" if person["auto"] else "sans réponse"


def level_of(person: Dict[str, Any], relation: str, interviewing: set, manual: List[str]) -> int:
    domain = person["email"].rsplit("@", 1)[-1]
    return trust_level(" ".join(person["sujets"]), person["envoyes"], person["recus"], relation,
                       person["source"] == "contact partagé", domain in interviewing, domain in FREE_MAIL,
                       person["email"] in manual or ("@" + domain in manual and person["recus"] > 0))


def assemble(people: Dict[str, Dict[str, Any]], bounced: List[str]) -> List[Dict[str, str]]:
    by_email, by_domain, interviewing = company_names()
    refusals, manual = contact_guard.load_refusals(), manual_opportunities()
    rows = []
    for person in people.values():
        first, last = split_name(person["affichage"], person["email"])
        verdict = contact_guard.check(person["email"], refusals)
        relation = relation_of(person, verdict)
        level = level_of(person, relation, interviewing, manual)
        rows.append({
            "prenom": first, "nom": last, "email": person["email"], "entreprise": company_of(person, by_email, by_domain),
            "fonction": person["fonction"], "telephone": person["telephone"],
            "statut": address_status(person["email"], person["envoyes"], person["recus"] + person["auto"], person["email"] in bounced,
                                     contact_guard.is_shared_domain(person["email"].rsplit("@", 1)[-1])
                                     and person["email"].rsplit("@", 1)[-1] not in FREE_MAIL),
            "relation": relation, "niveau": TRUST_LEVELS[level], "priorite": str(level),
            "premier": person["premier"], "dernier": person["dernier"], "envoyes": str(person["envoyes"]),
            "recus": str(person["recus"]), "sujet": person["sujet"], "source": person["source"], "cite_par": person["cite_par"],
        })
    return sorted(rows, key=lambda r: (r["priorite"], r["entreprise"].lower(), r["nom"].lower()))


def write_outputs(rows: List[Dict[str, str]], companies: List[Dict[str, str]]) -> None:
    os.makedirs(CSV_DIR, exist_ok=True)
    with open(NETWORK_PATH, "w", encoding="utf-8") as f:
        json.dump({"genere_le": date.today().isoformat(), "contacts": rows, "entreprises": companies}, f, ensure_ascii=False, indent=1)
    for name, data in (("contacts.csv", rows), ("entreprises.csv", companies)):
        with open(os.path.join(CSV_DIR, name), "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(data)


def build(since: str) -> None:
    from create_gmail_draft import get_gmail_service

    reader = GmailReader(get_gmail_service(), CACHE_PATH)
    people: Dict[str, Dict[str, Any]] = {}
    try:
        threads = collect_sent(reader, people, since)
        latest = collect_received(reader, people, threads, since)
        bounced = collect_bounces(reader, since)
        enrich_from_signatures(reader, people, latest)
    finally:
        reader.save()  # même interrompue, la lecture déjà faite n'est pas à refaire
    rows = assemble(people, bounced)
    companies = summarize_domains(rows)
    write_outputs(rows, companies)
    print(f"{len(rows)} contacts, {len(companies)} entreprises -> {NETWORK_PATH} et {CSV_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Réseau de contacts et formats d'adresse par entreprise.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Extrait les contacts depuis Gmail.")
    b.add_argument("--depuis", default="2026-04-01", help="Date de début (AAAA-MM-JJ).")
    a = sub.add_parser("adresse", help="Adresse probable d'une personne dans une entreprise connue.")
    a.add_argument("entreprise")
    a.add_argument("prenom")
    a.add_argument("nom")
    args = ap.parse_args()
    if args.cmd == "build":
        build(args.depuis)
    else:
        guess(args.entreprise, args.prenom, args.nom)


if __name__ == "__main__":
    main()
