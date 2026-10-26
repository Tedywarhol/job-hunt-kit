#!/usr/bin/env python3
"""Dossiers CV et lettre des candidatures spontanées IA : un dossier outputs/<slug>/ par entreprise.

Deux variantes selon le type d'équipe lu sur son profil et ses offres (leçon du 2026-10-14 : proposer de construire à une
équipe de chefs de projet métier tombe à côté) :
  construit : équipe tech, delivery ou conseil data. CV et lettre mettent en avant les assistants et automatisations
              construits (For You, assistant PLM, n8n).
  metier    : équipe qui pilote des projets métier. CV et lettre partent du stage de Business Analyst chez CANAL+ et des
              projets d'analyse (HR Analytics, sinistres), pour être le lien entre le métier et la data ou l'IA.
La lettre garde un squelette fixe (profil, outils, disponibilité) et deux passages propres à l'entreprise, écrits à la main
d'après des pages réellement lues : `accroche` (pourquoi cette équipe) et `cas_usage` (l'idée proposée, ou l'angle métier).

Usage : python scripts/prospection_dossier.py <fiches.json> [--build]
Une fiche : {"nom", "equipe" (construit|metier, défaut construit), "service" (facultatif), "accroche", "cas_usage",
"objet" (facultatif)}. `--build` lance ensuite build_application.py (CV et lettre en PDF, garde de tenue sur une page).
"""
import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from mail_lint import normaliser_typographie
from profile import date_lettre_aujourdhui, load_personal, ville_from_localisation
from prospection import slug
from prospection_plan import EQUIPES

RYTHME_LETTRE: str = ("Je suis en quatrième année du cycle ingénieur Data Science et IA à l'ECE Paris et je cherche une "
                      "alternance de deux ans, à raison de trois semaines en entreprise et trois semaines à l'école.")
VARIANTES: Dict[str, Dict[str, Any]] = {
    "construit": {
        "cv": {
            "titre": "Alternance 24 mois : IA, agents et automatisation",
            "accroche": "Élève ingénieur Data Science et IA : assistants RAG et automatisations construits en stage et pour des entreprises.",
            "projets_selection": ["Assistant IA connecté à un PLM industriel",
                                  "SaaS « Propulse » : Prospection & Scraping IA",
                                  "Workflow n8n : Automatisation Mails & CRM IA"],
            "competences_ordre": ["ia", "automatisation", "machine", "architectures"],
            "mots_cles_ats": ["Agents LLM", "RAG", "n8n", "MCP", "Alternance"],
        },
        "profil_lettre": (
            f"{RYTHME_LETTRE} Pendant mon stage d'AI Engineer, j'ai construit For You, une plateforme qui génère des "
            "chatbots à partir de documents (PDF, Word, Markdown, images). J'ai aussi réalisé un assistant qui interroge "
            "un PLM industriel en langage naturel, avec un agent LangChain et un backend FastAPI."),
        "objet": "Candidature spontanée en alternance : l'IA au service de vos équipes",
    },
    "metier": {
        "cv": {
            "titre": "Alternance 24 mois : Data et IA pour les métiers",
            "accroche": "Élève ingénieur Data Science et IA, passé par un stage de Business Analyst : je pars du besoin métier pour livrer des analyses utiles.",
            "projets_selection": ["Assistant IA connecté à un PLM industriel",
                                  "HR Analytics : Modélisation prédictive du turnover",
                                  "Analyse de l'inflation du coût de réparation des sinistres automobiles"],
            "competences_ordre": ["architectures", "machine", "ia", "automatisation"],
            "mots_cles_ats": ["Business Analyst", "Power BI", "Data", "IA", "Alternance"],
        },
        "profil_lettre": (
            f"{RYTHME_LETTRE} Lors de mon stage de Business Analyst chez CANAL+, j'ai conçu des tableaux de bord Power BI "
            "et fiabilisé le reporting destiné aux équipes marketing et à la direction. J'ai aussi construit des assistants "
            "IA à partir de documents d'entreprise, dont un chatbot pendant mon stage d'AI Engineer."),
        "objet": "Candidature spontanée en alternance : la data et l'IA au service de vos métiers",
    },
}
OUTILS_LETTRE: str = "Au quotidien, je travaille avec Claude, des serveurs MCP, n8n, Copilot Studio et Power Automate."
CLOTURE_LETTRE: str = ("Je suis disponible dès maintenant et je serais heureux d'en discuter avec vous, en visio ou sur "
                       "place.")


# Champs de texte libre : seuls eux reçoivent la typographie française. Les noms de projets (« projets_selection »)
# doivent rester identiques à ceux de cv-data.json pour être retrouvés.
CHAMPS_TEXTE_CV = ("titre", "accroche")
CHAMPS_TEXTE_LETTRE = ("objet", "paragraphes")


def typographier(contenu: Dict[str, Any], champs: tuple) -> Dict[str, Any]:
    """Applique la typographie française aux champs de texte nommés, sans toucher aux autres."""
    resultat = dict(contenu)
    for champ in champs:
        valeur = resultat.get(champ)
        if isinstance(valeur, str):
            resultat[champ] = normaliser_typographie(valeur)
        elif isinstance(valeur, list):
            resultat[champ] = [normaliser_typographie(v) if isinstance(v, str) else v for v in valeur]
    return resultat


def variante_de(fiche: Dict[str, Any]) -> Dict[str, Any]:
    equipe = fiche.get("equipe", "construit")
    if equipe not in EQUIPES:
        raise ValueError(f"Type d'équipe inconnu « {equipe} » : {', '.join(EQUIPES)}.")
    return VARIANTES[equipe]


def composer_cv_vars(fiche: Dict[str, Any]) -> Dict[str, Any]:
    cv = dict(variante_de(fiche)["cv"])
    cv["mots_cles_ats"] = [fiche["nom"], *cv["mots_cles_ats"]]
    return cv


def composer_lettre_vars(fiche: Dict[str, Any], date_lettre: str, ville_candidat: str) -> Dict[str, Any]:
    service = fiche.get("service", "")
    variante = variante_de(fiche)
    return {
        "type": "alternance", "entreprise": fiche["nom"], "service": service, "poste": "Alternance en IA",
        "destinataire": f"Madame, Monsieur de {service}" if service else "Madame, Monsieur",
        "date": date_lettre, "ville_candidat": ville_candidat, "objet": fiche.get("objet") or variante["objet"],
        "paragraphes": [fiche["accroche"], variante["profil_lettre"], f"{fiche['cas_usage']} {OUTILS_LETTRE}", CLOTURE_LETTRE],
    }


def ecrire_dossier(fiche: Dict[str, Any], racine: str = ROOT) -> str:
    """Écrit cv-vars.json et lettre-vars.json dans outputs/<slug>/ ; renvoie le slug."""
    for cle in ("nom", "accroche", "cas_usage"):
        if not str(fiche.get(cle, "")).strip():
            raise ValueError(f"Fiche incomplète : « {cle} » manquant.")
    variante_de(fiche)
    cle = slug(fiche["nom"])
    dossier = os.path.join(racine, "outputs", cle)
    os.makedirs(dossier, exist_ok=True)
    localisation = str(load_personal().get("localisation", "")).split(",")[0].strip() or ville_from_localisation()
    fichiers = {"cv-vars.json": typographier(composer_cv_vars(fiche), CHAMPS_TEXTE_CV),
                "lettre-vars.json": typographier(composer_lettre_vars(fiche, date_lettre_aujourdhui(), localisation),
                                                 CHAMPS_TEXTE_LETTRE)}
    for nom_fichier, contenu in fichiers.items():
        with open(os.path.join(dossier, nom_fichier), "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=2)
    return cle


def construire(cle: str) -> int:
    """Lance build_application.py ; code 0 si CV et lettre sont produits (3 : le CV ne tient pas sur une page)."""
    commande = [sys.executable, os.path.join(ROOT, "scripts", "build_application.py"), "--slug", cle, "--profile", "alternance"]
    return subprocess.run(commande, capture_output=True, text=True, timeout=300).returncode


def main() -> None:
    ap = argparse.ArgumentParser(description="Dossiers CV et lettre des candidatures spontanées IA.")
    ap.add_argument("fiches")
    ap.add_argument("--build", action="store_true")
    args = ap.parse_args()
    with open(args.fiches, encoding="utf-8") as f:
        fiches: List[Dict[str, Any]] = json.load(f)
    echecs = 0
    for fiche in fiches:
        try:
            cle = ecrire_dossier(fiche)
        except ValueError as erreur:
            print(f"REFUSÉE : {fiche.get('nom', '?')} ({erreur})")
            echecs += 1
            continue
        code = construire(cle) if args.build else None
        print(f"{cle} : dossier écrit" + ("" if code is None else f", construction code {code}"))
        echecs += 1 if code else 0
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
