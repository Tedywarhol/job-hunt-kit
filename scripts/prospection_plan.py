#!/usr/bin/env python3
"""Règles pures de la prospection spontanée : quotas par zone et par secteur, plan d'envoi sur sept jours.

Aucun appel réseau ni lecture de fichier : tout se teste sur des dictionnaires (tests/test_prospection_plan.py).
Conception : docs/plans/2026-10-14-candidatures-spontanees-design.md.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

QUOTAS_ZONES: Dict[str, int] = {
    "Île-de-France": 25, "Lyon": 12, "Nantes": 12, "Grenoble": 10, "Montpellier": 10,
    "Angers": 8, "Caen": 8, "Brest": 7, "La Rochelle": 5, "Bidart": 3,
}
QUOTAS_SECTEURS: Dict[str, int] = {"ia": 50, "utilisatrice": 50}
# Du moins exposé au plus exposé : la sonde est la personne dont une adresse fausse coûte le moins.
ROLES: Tuple[str, ...] = ("chef_projet", "manager", "directeur")
# Type d'équipe lu sur son profil et ses offres : elle construit (tech, delivery, conseil data) ou elle pilote des projets métier.
EQUIPES: Tuple[str, ...] = ("construit", "metier")
JOURS_ENVOI: int = 7
LINKEDIN_PAR_JOUR_MAX: int = 12
ADRESSE_SURE = ("sûre", "citée")
TYPE_ORDRE: Dict[str, int] = {"sonde": 0, "direct": 1, "compagnon": 2}


def repartition(entreprises: List[Dict[str, Any]]) -> Dict[str, Dict[str, Tuple[int, int]]]:
    """Pour chaque zone et chaque secteur : (nombre trouvé, nombre visé)."""
    zones = {z: (sum(1 for e in entreprises if e["ville"] == z), voulu) for z, voulu in QUOTAS_ZONES.items()}
    secteurs = {s: (sum(1 for e in entreprises if e["secteur"] == s), voulu) for s, voulu in QUOTAS_SECTEURS.items()}
    return {"zones": zones, "secteurs": secteurs}


def personnes_a_envoyer(entreprise: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [p for p in entreprise["personnes"] if p["canal"] == "mail" and p["statut"] == "brouillon"]


def choisir_sonde(personnes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """La personne la moins exposée parmi celles dont l'adresse est devinée."""
    devinees = [p for p in personnes if p["confiance"] not in ADRESSE_SURE]
    if not devinees:
        return None
    return min(devinees, key=lambda p: ROLES.index(p["role"]) if p["role"] in ROLES else len(ROLES))


def construire_elements(entreprises: List[Dict[str, Any]], aujourdhui: str) -> List[Dict[str, Any]]:
    """Un élément par mail à envoyer : direct (adresse sûre), sonde (une par entreprise à adresses devinées)
    ou compagnon (les autres, qui attendent 24 h sans rebond après la sonde).

    `aujourdhui` (AAAA-MM-JJ) sert à savoir si une sonde déjà envoyée a plus de 24 h : `libre_des` donne alors
    le premier jour (1 = aujourd'hui) où le compagnon peut partir.
    """
    elements: List[Dict[str, Any]] = []
    for entreprise in entreprises:
        personnes = personnes_a_envoyer(entreprise)
        sonde = choisir_sonde(personnes)
        partie = next(
            (p for p in entreprise["personnes"] if p["statut"] in ("envoye", "repondu") and p["confiance"] not in ADRESSE_SURE), None,
        )
        for personne in personnes:
            element: Dict[str, Any] = {"entreprise": entreprise["slug"], "adresse": personne["adresse"]}
            if personne["confiance"] in ADRESSE_SURE:
                element["type"] = "direct"
            elif partie is not None:
                element.update(type="compagnon", libre_des=1 if partie["date_envoi"] < aujourdhui else 2)
            else:
                element["type"] = "sonde" if personne is sonde else "compagnon"
            elements.append(element)
    return elements


def compagnon_bloque(element: Dict[str, Any], jour: int, jour_sonde: Dict[str, int]) -> bool:
    """Un compagnon ne part pas avant le lendemain de sa sonde (ou de son `libre_des` si la sonde est déjà partie)."""
    if element["type"] != "compagnon":
        return False
    if "libre_des" in element:
        return jour < element["libre_des"]
    return jour_sonde.get(element["entreprise"], jour) >= jour


def plan_mails(
    elements: List[Dict[str, Any]], jours: int = JOURS_ENVOI, capacite: Optional[int] = None,
) -> Tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Répartit les mails sur les jours : sondes d'abord, un compagnon seulement le jour suivant sa sonde.

    Renvoie (liste de jours, mails restés hors fenêtre). Capacité par jour, si elle n'est pas imposée :
    total / jours, arrondi au-dessus.
    """
    capacite = capacite or max(1, math.ceil(len(elements) / jours))
    restants = sorted(elements, key=lambda e: TYPE_ORDRE[e["type"]])
    jour_sonde: Dict[str, int] = {}
    planning: List[List[Dict[str, Any]]] = []
    for jour in range(1, jours + 1):
        du_jour: List[Dict[str, Any]] = []
        for element in restants:
            if len(du_jour) >= capacite:
                break
            if compagnon_bloque(element, jour, jour_sonde):
                continue
            du_jour.append(element)
            if element["type"] == "sonde":
                jour_sonde[element["entreprise"]] = jour
        restants = [e for e in restants if e not in du_jour]
        planning.append(du_jour)
    return planning, restants


def plan_linkedin(personnes: List[Dict[str, Any]], jours: int = JOURS_ENVOI) -> List[List[Dict[str, Any]]]:
    """Répartit les invitations LinkedIn à parts égales ; jamais plus de LINKEDIN_PAR_JOUR_MAX par jour."""
    planning: List[List[Dict[str, Any]]] = [[] for _ in range(jours)]
    for index, personne in enumerate(personnes):
        planning[index % jours].append(personne)
    if any(len(jour) > LINKEDIN_PAR_JOUR_MAX for jour in planning):
        raise ValueError(f"Plus de {LINKEDIN_PAR_JOUR_MAX} invitations LinkedIn par jour : allonger la fenêtre.")
    return planning
