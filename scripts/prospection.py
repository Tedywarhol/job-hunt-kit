#!/usr/bin/env python3
"""Candidatures spontanées IA : état des entreprises et des personnes, adresses, envois, plan sur sept jours.

Conception : docs/plans/2026-10-14-candidatures-spontanees-design.md. L'état vit dans state/prospection.json
(donnée personnelle, jamais versionnée). Rien ici n'envoie un mail : les brouillons sont créés par
`prospection_gmail.py`, le candidat envoie lui-même, puis déclare l'envoi (`envoye`) ou le fait détecter (`sync-envois`).

Usage :
  python scripts/prospection.py ajouter-entreprise --nom "Acme Aero" --ville Lyon --secteur ia --domaine acme-aero.com
  python scripts/prospection.py ajouter-personne acme-aero --prenom Jeanne --nom Martin --role manager --fonction "..." --linkedin URL
  python scripts/prospection.py etat | plan | envoye <adresse> [--date AAAA-MM-JJ] | rebond <adresse>
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import contact_guard
import network_lookup
from network_patterns import FORMATS, build_address
from prospection_plan import (EQUIPES, QUOTAS_SECTEURS, QUOTAS_ZONES, ROLES, construire_elements, plan_linkedin, plan_mails,
                              repartition)
from followups_spontanee import nom_affiche
from run_followups import SEQUENCE_SPONTANEE, load_outreach, save_outreach

STATE_PATH: str = os.path.join(ROOT, "state", "prospection.json")
STATUTS_PERSONNE = ("repere", "brouillon", "envoye", "repondu", "rebond", "a_refaire", "ecarte")
POSTE_SPONTANEE: str = "alternance en IA"
CHAMPS_PERSONNE = ("prenom", "nom", "role", "fonction", "linkedin", "adresse", "confiance", "canal", "statut")


def signature_mail(personal: Dict[str, Any]) -> str:
    """Bloc de signature des premiers mails : nom d'affichage, puis téléphone s'il existe."""
    lignes = [nom_affiche(str(personal.get("nom", ""))), str(personal.get("telephone", ""))]
    return "\n".join(ligne for ligne in lignes if ligne)


def slug(nom: str) -> str:
    ascii_nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_nom).strip("-")


def valider(state: Dict[str, Any]) -> None:
    """Échoue tôt sur un état incohérent (fichier modifié à la main, version ancienne)."""
    if not isinstance(state.get("entreprises"), dict):
        raise ValueError("state/prospection.json : clé « entreprises » absente ou mal formée.")
    for cle, entreprise in state["entreprises"].items():
        if entreprise.get("slug") != cle:
            raise ValueError(f"Entreprise « {cle} » : slug incohérent ({entreprise.get('slug')!r}).")
        if entreprise.get("ville") not in QUOTAS_ZONES or entreprise.get("secteur") not in QUOTAS_SECTEURS:
            raise ValueError(f"Entreprise « {cle} » : ville ou secteur inconnu.")
        if entreprise.get("equipe", "construit") not in EQUIPES:
            raise ValueError(f"Entreprise « {cle} » : type d'équipe inconnu ({entreprise.get('equipe')!r}).")
        for personne in entreprise.get("personnes", []):
            manquants = [c for c in CHAMPS_PERSONNE if c not in personne]
            if manquants or personne["statut"] not in STATUTS_PERSONNE:
                raise ValueError(f"Entreprise « {cle} » : personne incomplète ou statut inconnu ({manquants}).")


def charger(path: str = STATE_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"entreprises": {}}
    with open(path, encoding="utf-8") as f:
        state: Dict[str, Any] = json.load(f)
    valider(state)
    return state


def sauver(state: Dict[str, Any], path: str = STATE_PATH) -> None:
    valider(state)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def ajouter_entreprise(state: Dict[str, Any], nom: str, ville: str, secteur: str, domaine: str,
                       site: str = "", cas_usage: str = "", equipe: str = "construit") -> Dict[str, Any]:
    if ville not in QUOTAS_ZONES:
        raise ValueError(f"Ville inconnue « {ville} » : {', '.join(QUOTAS_ZONES)}.")
    if secteur not in QUOTAS_SECTEURS:
        raise ValueError(f"Secteur inconnu « {secteur} » : {', '.join(QUOTAS_SECTEURS)}.")
    if equipe not in EQUIPES:
        raise ValueError(f"Type d'équipe inconnu « {equipe} » : {', '.join(EQUIPES)}.")
    cle = slug(nom)
    if cle in state["entreprises"]:
        raise ValueError(f"« {nom} » existe déjà ({cle}).")
    entreprise = {"slug": cle, "nom": nom, "ville": ville, "secteur": secteur,
                  "domaine": domaine.strip().lower().removeprefix("www."), "site": site,
                  "cas_usage": cas_usage, "equipe": equipe, "personnes": []}
    state["entreprises"][cle] = entreprise
    return entreprise


def proposer_adresse(domaine: str, prenom: str, nom: str, connues: List[Dict[str, str]]) -> Tuple[Optional[str], str]:
    """(adresse, confiance) : « sûre » si le format du domaine est établi dans la base du réseau, sinon « devinée »
    (prenom.nom par défaut). Un nom composé (espace, trait d'union, apostrophe) reste « devinée » même sur un format
    sûr : l'entreprise peut écrire « el.amrani », « elamrani » ou « el-amrani ». Sans domaine ou sans nom : (None, « aucune »)."""
    if not domaine:
        return None, "aucune"
    societe = next((c for c in connues if c["domaine"] == domaine), None)
    format_connu = societe["format"] if societe else ""
    adresse = build_address(format_connu or FORMATS[0][0], prenom, nom, domaine)
    if adresse is None:
        return None, "aucune"
    nom_simple = not re.search(r"[\s'’-]", f"{prenom.strip()}{nom.strip()}")
    sure = bool(societe and societe["confiance"] == "sûre" and format_connu and nom_simple)
    return adresse, "sûre" if sure else "devinée"


def ajouter_personne(state: Dict[str, Any], cle: str, prenom: str, nom: str, role: str, fonction: str, linkedin: str,
                     refusals: Dict[str, List[Dict[str, str]]], connues: List[Dict[str, str]],
                     adresse: str = "", forcer: bool = False, incertain: bool = False) -> Dict[str, Any]:
    """Ajoute une personne repérée. Adresse donnée : « citée ». Sinon proposée d'après le réseau. Un refus antérieur
    (contact_guard) écarte la personne, sauf `forcer`. `incertain` (nom de famille incomplet ou déduit d'une URL) garde
    l'adresse « devinée » même sur un format sûr. Sans adresse, le canal est LinkedIn."""
    if role not in ROLES:
        raise ValueError(f"Rôle inconnu « {role} » : {', '.join(ROLES)}.")
    entreprise = state["entreprises"][cle]
    if adresse:
        trouvee, confiance = adresse.strip().lower(), "citée"
    else:
        trouvee, confiance = proposer_adresse(entreprise["domaine"], prenom, nom, connues)
        confiance = "devinée" if incertain and confiance == "sûre" else confiance
    verdict = contact_guard.check(trouvee, refusals) if trouvee else None
    personne: Dict[str, Any] = {
        "prenom": prenom, "nom": nom, "role": role, "fonction": fonction, "linkedin": linkedin,
        "adresse": trouvee or "", "confiance": confiance, "canal": "mail" if trouvee else "linkedin",
        "statut": "repere", "avertissement": verdict["raison"] if verdict else "",
    }
    if verdict and not forcer:
        personne.update(canal="aucun", statut="ecarte")
    entreprise["personnes"].append(personne)
    return personne


def trouver_personne(state: Dict[str, Any], adresse: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cible = adresse.strip().lower()
    for entreprise in state["entreprises"].values():
        for personne in entreprise["personnes"]:
            if personne["adresse"] == cible:
                return entreprise, personne
    raise ValueError(f"Aucune personne avec l'adresse {adresse}.")


def entree_outreach(entreprise: Dict[str, Any], personne: Dict[str, Any], date_envoi: str) -> Dict[str, Any]:
    """Même forme que les autres entrées de state/outreach.json, ancrée sur la date d'ENVOI réelle (pas celle du
    brouillon) : sinon les relances partiraient avant que le mail ne soit parti."""
    return {
        "email": personne["adresse"], "entreprise": entreprise["nom"], "poste": POSTE_SPONTANEE, "numero_offre": "",
        "etape": "J+0", "brouillon_id": personne.get("brouillon_id", ""), "date_creation_brouillon": date_envoi,
        "statut": "Envoyé", "date_j0": date_envoi, "relances": [], "prenom": personne["prenom"],
        "objet": personne.get("objet", ""), "type": "spontanee", "sequence": list(SEQUENCE_SPONTANEE), "sans_notion": True,
    }


def marquer_envoye(state: Dict[str, Any], outreach: List[Dict[str, Any]], adresse: str, date_envoi: str) -> bool:
    """Passe la personne à « envoye » et l'inscrit pour les relances. Faux si l'adresse était déjà suivie."""
    entreprise, personne = trouver_personne(state, adresse)
    personne.update(statut="envoye", date_envoi=date_envoi)
    if any(e.get("email") == personne["adresse"] for e in outreach):
        return False
    outreach.append(entree_outreach(entreprise, personne, date_envoi))
    return True


def marquer_reponse(state: Dict[str, Any], outreach: List[Dict[str, Any]], adresse: str, thread_id: str = "") -> None:
    """Une réponse arrête les relances de cette personne et prouve que l'adresse existe (les collègues aux adresses
    devinées de la même entreprise peuvent alors partir)."""
    _, personne = trouver_personne(state, adresse)
    personne["statut"] = "repondu"
    for entree in outreach:
        if entree.get("email") == personne["adresse"]:
            entree.update(etape="Réponse reçue", statut="Réponse reçue", thread_id=thread_id)


def marquer_rebond(state: Dict[str, Any], adresse: str) -> int:
    """Rebond : la personne passe en « rebond » et ses collègues aux adresses devinées en « a_refaire » (leur format
    est probablement faux aussi). Renvoie le nombre de collègues remis à refaire."""
    entreprise, personne = trouver_personne(state, adresse)
    personne["statut"] = "rebond"
    refaits = [p for p in entreprise["personnes"]
               if p is not personne and p["confiance"] == "devinée" and p["statut"] in ("repere", "brouillon")]
    for autre in refaits:
        autre["statut"] = "a_refaire"
    return len(refaits)


def lignes_etat(state: Dict[str, Any]) -> List[str]:
    entreprises = list(state["entreprises"].values())
    rep = repartition(entreprises)
    lignes = [f"{len(entreprises)} entreprise(s), {sum(len(e['personnes']) for e in entreprises)} personne(s)"]
    lignes += [f"  {z:<13} {a}/{v}" for z, (a, v) in rep["zones"].items()]
    lignes += [f"  secteur {s:<13} {a}/{v}" for s, (a, v) in rep["secteurs"].items()]
    comptes: Dict[str, int] = {}
    for entreprise in entreprises:
        for personne in entreprise["personnes"]:
            comptes[personne["statut"]] = comptes.get(personne["statut"], 0) + 1
    return lignes + [f"  personnes {statut:<10} {n}" for statut, n in sorted(comptes.items())]


def lignes_plan(state: Dict[str, Any], aujourdhui: str) -> List[str]:
    entreprises = list(state["entreprises"].values())
    planning, restants = plan_mails(construire_elements(entreprises, aujourdhui))
    lignes: List[str] = []
    for jour, mails in enumerate(planning, start=1):
        genres = {t: sum(1 for m in mails if m["type"] == t) for t in ("sonde", "direct", "compagnon")}
        lignes.append(f"Jour {jour} : {len(mails)} mail(s) (sondes {genres['sonde']}, directs {genres['direct']}, "
                      f"compagnons {genres['compagnon']})")
    linkedin = [p for e in entreprises for p in e["personnes"] if p["canal"] == "linkedin" and p["statut"] != "envoye"]
    lignes += [f"LinkedIn, jour {i} : {len(j)} invitation(s)" for i, j in enumerate(plan_linkedin(linkedin), start=1)]
    if restants:
        lignes.append(f"Hors fenêtre de 7 jours : {len(restants)} mail(s)")
    return lignes


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Candidatures spontanées IA : état et plan d'envoi.")
    sub = p.add_subparsers(dest="commande", required=True)
    e = sub.add_parser("ajouter-entreprise")
    e.add_argument("--nom", required=True)
    e.add_argument("--ville", required=True)
    e.add_argument("--secteur", required=True)
    e.add_argument("--domaine", required=True, help="Domaine des adresses mail (acme-aero.com)")
    e.add_argument("--site", default="")
    e.add_argument("--cas-usage", default="")
    e.add_argument("--equipe", default="construit", help="construit (tech, delivery) ou metier (chefs de projet métier)")
    q = sub.add_parser("ajouter-personne")
    q.add_argument("entreprise", help="slug de l'entreprise")
    for champ in ("prenom", "nom", "role", "fonction", "linkedin"):
        q.add_argument(f"--{champ}", required=True)
    q.add_argument("--adresse", default="", help="Adresse lue sur une source publique (sinon proposée)")
    q.add_argument("--forcer", action="store_true", help="Garder la personne malgré un refus antérieur")
    sub.add_parser("importer").add_argument("fiches", help="JSON : une fiche par entreprise (prospection_import.py)")
    sub.add_parser("etat")
    sub.add_parser("plan")
    s = sub.add_parser("envoye")
    s.add_argument("adresse")
    s.add_argument("--date", default=date.today().isoformat())
    sub.add_parser("rebond").add_argument("adresse")
    r = sub.add_parser("reponse")
    r.add_argument("adresse")
    r.add_argument("--fil", default="", help="Identifiant du fil Gmail de la réponse")
    return p


def main() -> None:
    args = parser().parse_args()
    state = charger()
    try:
        if args.commande == "ajouter-entreprise":
            ajouter_entreprise(state, args.nom, args.ville, args.secteur, args.domaine, args.site, args.cas_usage, args.equipe)
        elif args.commande == "ajouter-personne":
            personne = ajouter_personne(state, args.entreprise, args.prenom, args.nom, args.role, args.fonction,
                                        args.linkedin, contact_guard.load_refusals(), network_lookup.known_companies(),
                                        args.adresse, args.forcer)
            print(f"{personne['prenom']} {personne['nom']} : {personne['adresse'] or 'aucune adresse'} "
                  f"({personne['confiance']}, canal {personne['canal']}) {personne['avertissement']}")
        elif args.commande == "importer":
            from prospection_import import importer
            with open(args.fiches, encoding="utf-8") as f:
                rapport = importer(state, json.load(f), contact_guard.load_refusals(), network_lookup.known_companies())
            print("\n".join(rapport))
        elif args.commande == "envoye":
            outreach = load_outreach()
            suivi = marquer_envoye(state, outreach, args.adresse, args.date)
            save_outreach(outreach)
            print("Envoi enregistré, relances suivies." if suivi else "Envoi enregistré (déjà suivi dans outreach.json).")
        elif args.commande == "reponse":
            outreach = load_outreach()
            marquer_reponse(state, outreach, args.adresse, args.fil)
            save_outreach(outreach)
            print("Réponse enregistrée, relances arrêtées.")
        elif args.commande == "rebond":
            print(f"Rebond noté, {marquer_rebond(state, args.adresse)} collègue(s) à refaire.")
        else:
            print("\n".join(lignes_etat(state) if args.commande == "etat" else lignes_plan(state, date.today().isoformat())))
            return
    except (ValueError, KeyError) as erreur:
        sys.exit(f"Erreur : {erreur}")
    sauver(state)


if __name__ == "__main__":
    main()
