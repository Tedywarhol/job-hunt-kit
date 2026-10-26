#!/usr/bin/env python3
"""Import par lot dans state/prospection.json des entreprises et des personnes repérées.

Une fiche par entreprise, écrite à partir de pages LinkedIn réellement lues :
  {"nom", "ville", "secteur", "domaine", "site", "cas_usage", "equipe" (construit|metier, défaut construit),
   "personnes": [{"prenom", "nom", "role", "fonction", "linkedin", "adresse", "forcer", "incertain" (facultatifs)}]}
Une entreprise en erreur (ville inconnue, rôle inconnu...) est retirée en entier et signalée : le reste du lot passe.
Usage : python scripts/prospection.py importer <fiches.json>
"""
from typing import Any, Dict, List

from prospection import ajouter_entreprise, ajouter_personne, slug


def importer_fiche(state: Dict[str, Any], fiche: Dict[str, Any], refusals: Dict[str, Any],
                   connues: List[Dict[str, str]]) -> List[str]:
    """Ajoute une entreprise et ses personnes ; renvoie une ligne de rapport par personne."""
    cle = slug(fiche["nom"])
    ajouter_entreprise(state, fiche["nom"], fiche["ville"], fiche["secteur"], fiche["domaine"],
                       fiche.get("site", ""), fiche.get("cas_usage", ""), fiche.get("equipe", "construit"))
    lignes: List[str] = []
    for p in fiche["personnes"]:
        personne = ajouter_personne(state, cle, p["prenom"], p["nom"], p["role"], p["fonction"], p["linkedin"],
                                    refusals, connues, p.get("adresse", ""), bool(p.get("forcer")), bool(p.get("incertain")))
        reserve = f" [{personne['avertissement']}]" if personne["avertissement"] else ""
        lignes.append(f"{fiche['nom']} / {p['prenom']} {p['nom']} : {personne['adresse'] or 'aucune adresse'} "
                      f"({personne['confiance']}, {personne['statut']}){reserve}")
    return lignes


def importer(state: Dict[str, Any], fiches: List[Dict[str, Any]], refusals: Dict[str, Any],
             connues: List[Dict[str, str]]) -> List[str]:
    rapport: List[str] = []
    for fiche in fiches:
        cle = slug(str(fiche.get("nom", "")))
        if cle in state["entreprises"]:
            rapport.append(f"déjà présente, ignorée : {fiche['nom']}")
            continue
        try:
            rapport += importer_fiche(state, fiche, refusals, connues)
        except (ValueError, KeyError) as erreur:
            state["entreprises"].pop(cle, None)
            rapport.append(f"REFUSÉE : {fiche.get('nom', '?')} ({erreur})")
    return rapport
