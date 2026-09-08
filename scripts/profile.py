#!/usr/bin/env python3
"""Source unique de l'identité utilisateur : lit `personal` dans templates/cv/cv-data.json.

Tout script qui a besoin du nom / email / téléphone / LinkedIn de l'utilisateur
doit passer par ici — jamais de valeur personnelle en dur.
"""
from datetime import date
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_DATA: str = os.path.join(ROOT, "templates", "cv", "cv-data.json")


def load_cv_data(path: Optional[str] = None) -> Dict[str, Any]:
    target_path = path or CV_DATA
    try:
        with open(target_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Erreur claire plutôt qu'un traceback brut : cas typique d'une machine fraîche
        # où python scripts/init.py n'a pas encore été lancé (cf. audit 2026-09-08).
        sys.exit(
            f"Profil introuvable : {target_path}\n"
            "Lancez d'abord : python scripts/init.py (ou python hunt.py init)"
        )


def load_personal(path: Optional[str] = None) -> Dict[str, Any]:
    return load_cv_data(path).get("personal", {})


def doc_base_names(personal: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Bases de noms de fichiers : (CV_Prenom_NOM, Lettre_Prenom_NOM)."""
    p = personal or load_personal()
    prenom = (p.get("prenom") or "").strip().title()
    nom = (p.get("nom_famille") or "").strip().upper()
    if not prenom and not nom:
        full = (p.get("nom") or "Candidat").strip()
        parts = full.split()
        prenom = parts[0].title() if parts else "Candidat"
        nom = ("_".join(parts[1:]) if len(parts) > 1 else prenom).upper()
    elif not prenom:
        prenom = "Candidat"
    elif not nom:
        nom = prenom.upper()
    prenom = prenom.replace(" ", "_")
    nom = nom.replace(" ", "_")
    return f"CV_{prenom}_{nom}", f"Lettre_{prenom}_{nom}"


def ville_from_localisation(personal: Optional[Dict[str, Any]] = None, default: str = "Paris") -> str:
    """'Paris (75), France' → 'Paris'."""
    p = personal or load_personal()
    loc = (p.get("localisation") or "").split(",")[0].strip()
    loc = loc.split("(")[0].strip()
    return loc or default


def mois_francais(d: Any) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    m = d.month if hasattr(d, "month") else int(d)
    return mois[m - 1]


def date_lettre_aujourdhui() -> str:
    """'1er septembre 2026' format pour l'en-tête de lettre."""
    d = date.today()
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {mois_francais(d)} {d.year}"

