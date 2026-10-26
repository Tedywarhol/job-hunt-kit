#!/usr/bin/env python3
"""Candidatures spontanées IA côté Gmail : contrôle d'un lot, brouillons, détection des envois et des rebonds.

Jamais d'envoi : seuls des brouillons sont créés, le candidat envoie lui-même. Un lot est un JSON
`[{"entreprise": slug, "adresse": ..., "objet": ..., "corps": ...}, ...]` (une entrée par personne, mail écrit à la main).
Tout le lot est contrôlé avant le moindre brouillon (refus, mail déjà envoyé, ton, pièces jointes) ; un seul problème
bloque toute la création.

Usage :
  python scripts/prospection_gmail.py brouillons --lot outputs/prospection/vague-1.json [--apply] [--orthographe]
  python scripts/prospection_gmail.py sync-envois [--apply]       # envois et rebonds détectés dans Gmail
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_human_tone
import contact_guard
import mail_lint
import prospection
from create_gmail_draft import create_draft, get_gmail_service
from profile import doc_base_names, load_personal
from run_followups import load_outreach, save_outreach

CLES_MAIL = ("entreprise", "adresse", "objet", "corps")
SONDE_REBOND_JOURS = 3


def lire_lot(chemin: str) -> List[Dict[str, str]]:
    """Charge le lot et remplace `{signature}` par la signature du profil. Un autre `{...}` oublié bloque le lot."""
    with open(chemin, encoding="utf-8") as f:
        lot = json.load(f)
    if not isinstance(lot, list) or not lot:
        raise ValueError("Le lot doit être une liste non vide de mails.")
    signature = prospection.signature_mail(load_personal())
    for rang, mail in enumerate(lot, start=1):
        manquants = [c for c in CLES_MAIL if not str(mail.get(c, "")).strip()]
        if manquants:
            raise ValueError(f"Mail {rang} : champs manquants {manquants}.")
        mail["corps"] = mail["corps"].replace("{signature}", signature)
        if re.search(r"[{}]", mail["corps"] + mail["objet"]):
            raise ValueError(f"Mail {rang} : un champ {{...}} n'est pas rempli.")
        mail["corps"] = mail_lint.normaliser_typographie(mail["corps"])
        mail["objet"] = mail_lint.normaliser_typographie(mail["objet"])
    return lot


def pieces_jointes(cle: str) -> List[str]:
    """CV et lettre PDF du dossier outputs/<slug>/, fabriqués par build_application.py."""
    return [os.path.join(ROOT, "outputs", cle, f"{base}.pdf") for base in doc_base_names()]


def dernier_envoi(service: Any, adresse: str, apres: Optional[str] = None) -> Optional[str]:
    """Date (AAAA-MM-JJ) du dernier mail envoyé à cette adresse, dans TOUS les fils ; None si jamais écrit."""
    requete = f"in:sent to:{adresse}" + (f" after:{apres.replace('-', '/')}" if apres else "")
    reponse = service.users().messages().list(userId="me", q=requete, maxResults=1).execute()
    messages = reponse.get("messages", [])
    if not messages:
        return None
    meta = service.users().messages().get(userId="me", id=messages[0]["id"], format="metadata").execute()
    return datetime.fromtimestamp(int(meta["internalDate"]) / 1000).date().isoformat()


def a_rebondi(service: Any, adresse: str, depuis: str) -> bool:
    """Un message d'erreur de remise (mailer-daemon, postmaster) cite-t-il cette adresse depuis `depuis` ?"""
    requete = f'from:(mailer-daemon OR postmaster) "{adresse}" after:{depuis.replace("-", "/")}'
    return bool(service.users().messages().list(userId="me", q=requete, maxResults=1).execute().get("messages"))


def problemes_mail(mail: Dict[str, str], state: Dict[str, Any], refusals: Dict[str, Any], service: Any) -> List[str]:
    adresse = mail["adresse"].strip().lower()
    try:
        _, personne = prospection.trouver_personne(state, adresse)
    except ValueError as erreur:
        return [str(erreur)]
    problemes: List[str] = []
    if personne["canal"] != "mail" or personne["statut"] not in ("repere", "a_refaire"):
        problemes.append(f"{adresse} : canal {personne['canal']}, statut {personne['statut']} (pas de brouillon à créer).")
    verdict = contact_guard.check(adresse, refusals)
    if verdict:
        problemes.append(f"{adresse} : garde-fou ({verdict['niveau']}) {verdict['raison']}")
    envoi = dernier_envoi(service, adresse)
    if envoi:
        problemes.append(f"{adresse} : un mail lui a déjà été envoyé le {envoi}.")
    manquantes = [p for p in pieces_jointes(mail["entreprise"]) if not os.path.isfile(p)]
    if manquantes:
        problemes.append(f"{adresse} : pièces jointes absentes {[os.path.basename(p) for p in manquantes]}.")
    return problemes


def verifier_lot(lot: List[Dict[str, str]], state: Dict[str, Any], service: Any, orthographe: bool) -> List[str]:
    refusals = contact_guard.load_refusals()
    problemes = [p for mail in lot for p in problemes_mail(mail, state, refusals, service)]
    adresses = [m["adresse"].strip().lower() for m in lot]
    problemes += [f"{a} : présente deux fois dans le lot." for a in sorted({a for a in adresses if adresses.count(a) > 1})]
    if not check_human_tone.rapport_lot({m["adresse"]: m["corps"] for m in lot}, orthographe):
        problemes.append("Contrôle de ton du lot : voir le rapport ci-dessus.")
    return problemes


def creer_brouillons(lot: List[Dict[str, str]], state: Dict[str, Any], service: Any) -> int:
    """Crée un brouillon par mail (CV et lettre joints) et enregistre l'état après chacun, pour qu'une panne en
    cours de route ne laisse jamais un brouillon sans trace."""
    expediteur = load_personal().get("email")
    for mail in lot:
        _, personne = prospection.trouver_personne(state, mail["adresse"])
        brouillon = create_draft(service, mail["adresse"].strip(), mail["objet"], mail["corps"],
                                 attachment_paths=pieces_jointes(mail["entreprise"]), from_email=expediteur)
        personne.update(statut="brouillon", brouillon_id=brouillon.get("id", ""), objet=mail["objet"],
                        date_brouillon=date.today().isoformat())
        prospection.sauver(state)
    return len(lot)


def sonde_recente(personne: Dict[str, Any]) -> bool:
    return (date.today() - date.fromisoformat(personne["date_envoi"])).days <= SONDE_REBOND_JOURS


def detecter_personne(personne: Dict[str, Any], state: Dict[str, Any], service: Any,
                      outreach: List[Dict[str, Any]], appliquer: bool) -> Optional[str]:
    adresse = personne["adresse"]
    if personne["statut"] == "brouillon":
        envoi = dernier_envoi(service, adresse, personne.get("date_brouillon"))
        if not envoi:
            return None
        if appliquer:
            prospection.marquer_envoye(state, outreach, adresse, envoi)
        return f"Envoyé le {envoi} : {adresse}"
    if personne["statut"] == "envoye" and personne["confiance"] == "devinée" and sonde_recente(personne)             and a_rebondi(service, adresse, personne["date_envoi"]):
        if appliquer:
            prospection.marquer_rebond(state, adresse)
        return f"REBOND : {adresse}"
    return None


def detecter(state: Dict[str, Any], service: Any, outreach: List[Dict[str, Any]], appliquer: bool) -> List[str]:
    """Envois (brouillon devenu mail envoyé) et rebonds récents (sondes) à partir de Gmail."""
    rapport = [detecter_personne(p, state, service, outreach, appliquer)
               for e in state["entreprises"].values() for p in e["personnes"]]
    return [ligne for ligne in rapport if ligne]


def main() -> None:
    ap = argparse.ArgumentParser(description="Brouillons Gmail et détection des envois (spontanées IA).")
    sub = ap.add_subparsers(dest="commande", required=True)
    b = sub.add_parser("brouillons")
    b.add_argument("--lot", required=True)
    b.add_argument("--apply", action="store_true", help="Crée réellement les brouillons (sinon simple contrôle)")
    b.add_argument("--orthographe", action="store_true")
    s = sub.add_parser("sync-envois")
    s.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    state, service = prospection.charger(), get_gmail_service()
    if args.commande == "brouillons":
        lot = lire_lot(args.lot)
        problemes = verifier_lot(lot, state, service, args.orthographe)
        print("\n".join(problemes) if problemes else f"Lot propre : {len(lot)} mail(s).")
        if problemes:
            sys.exit(2)
        print(f"{creer_brouillons(lot, state, service)} brouillon(s) créé(s)." if args.apply else "Contrôle seul (ajouter --apply).")
        return
    outreach = load_outreach()
    print("\n".join(detecter(state, service, outreach, args.apply)) or "Rien de nouveau.")
    if args.apply:
        save_outreach(outreach)
        prospection.sauver(state)


if __name__ == "__main__":
    main()
