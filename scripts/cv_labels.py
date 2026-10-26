#!/usr/bin/env python3
"""Libellés du CV et de la lettre par langue, et fichier de données associé (2026-10-18).

Le gabarit était figé en français. Une candidature en anglais (Aptiv, Apple) demande des titres de rubrique
anglais, `<html lang="en">` et le maître `cv-data.en.json`. La langue se règle par `"langue": "en"` dans
`cv-vars.json` et `lettre-vars.json` ; sans cette clé, le rendu français reste strictement identique.
"""
import os
from typing import Dict

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_DIR: str = os.path.join(ROOT, "templates", "cv")
LANGUE_DEFAUT: str = "fr"

LIBELLES: Dict[str, Dict[str, str]] = {
    "fr": {
        "html_lang": "fr",
        "contact": "Contact",
        "formation": "Formation",
        "competences": "Compétences clés",
        "stack": "Stack technique",
        "savoir_etre": "Savoir-être",
        "langues": "Langues",
        "certifications": "Certifications",
        "interets": "Intérêts",
        "profil": "Profil & Adéquation",
        "experiences": "Expériences professionnelles",
        "projets": "Projets d'envergure",
        "projets_autres": "Projets",
        "cv_titre": "CV",
        "candidature": "Candidature",
        "lettre_titre": "Lettre de Motivation",
        "lettre_pdf": "Lettre de motivation",
        "objet": "Objet :",
        "destinataire": "Madame, Monsieur",
        "lieu_date": "{ville}, le {date}",
        "formule": "Je vous prie d'agréer, {salut}, l'expression de mes salutations distinguées.",
        "role_defaut": "Alternance Data Science & IA",
    },
    "en": {
        "html_lang": "en",
        "contact": "Contact",
        "formation": "Education",
        "competences": "Key Skills",
        "stack": "Technical Skills",
        "savoir_etre": "Soft Skills",
        "langues": "Languages",
        "certifications": "Certifications & Training",
        "interets": "Interests",
        "profil": "Profile",
        "experiences": "Professional Experience",
        "projets": "Projects",
        "projets_autres": "Projects",
        "cv_titre": "Resume",
        "candidature": "Application",
        "lettre_titre": "Cover Letter",
        "lettre_pdf": "Cover letter",
        "objet": "Subject:",
        "destinataire": "Dear Hiring Team",
        "lieu_date": "{ville}, {date}",
        "formule": "Kind regards,",
        "role_defaut": "Data Science & AI Internship",
    },
}


def libelles(langue: str = LANGUE_DEFAUT) -> Dict[str, str]:
    """Libellés de `langue`. Une langue inconnue est une erreur : mieux vaut échouer qu'un CV à moitié traduit."""
    try:
        return LIBELLES[langue]
    except KeyError:
        raise ValueError(f"Langue inconnue : {langue!r} (attendu : {', '.join(LIBELLES)})") from None


def fichier_donnees(langue: str = LANGUE_DEFAUT) -> str:
    """Chemin du CV maître de `langue` : cv-data.json en français, cv-data.<langue>.json sinon."""
    libelles(langue)
    nom = "cv-data.json" if langue == LANGUE_DEFAUT else f"cv-data.{langue}.json"
    return os.path.join(CV_DIR, nom)
