#!/usr/bin/env python3
"""Relances des candidatures spontanées IA (type « spontanee » dans state/outreach.json).

Le moteur `run_followups.py` garde ses modèles « candidature au poste de X » pour les offres. Une candidature
spontanée n'a pas de poste : ces modèles reprennent la situation J de config/outreach-situations.md (relance simple,
sept jours au moins entre deux mails, trois mails au plus par personne et par mois), avec le prénom et la date du
premier message. Pas de tiret cadratin, pas de « & ».
"""
from datetime import datetime
from typing import Any, Dict

from mail_lint import normaliser_typographie

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")

TEMPLATES: Dict[str, str] = {
    "J+7": (
        "Bonjour {prenom},\n\n"
        "Je reviens une fois vers vous au sujet de mon message du {date}, au cas où il serait passé inaperçu. "
        "Je cherche toujours une alternance en IA de 24 mois, et l'échange que je proposais reste d'actualité de mon côté.\n\n"
        "Auriez-vous un retour, même bref ? Si ce n'est pas le bon moment, dites-le-moi simplement, je comprendrai.\n\n"
        "Merci, et bonne journée.\n\n"
        "Bien cordialement,\n{nom}"
    ),
    "J+14": (
        "Bonjour {prenom},\n\n"
        "Je n'ai pas eu de retour à mes deux messages et je ne veux pas vous importuner : celui-ci sera le dernier. "
        "Si une alternance en IA peut un jour avoir sa place dans votre équipe, ou si un collègue est mieux placé "
        "que vous pour en parler, un mot de votre part me suffirait.\n\n"
        "Merci pour votre temps, et très bonne continuation.\n\n"
        "Bien cordialement,\n{nom}"
    ),
}


def nom_affiche(nom: str) -> str:
    """« Jeanne DUPONT » -> « Jeanne Dupont » : le profil met le nom de famille en majuscules, pas la signature."""
    return " ".join(mot.title() if len(mot) > 1 and mot.isupper() else mot for mot in nom.split())


def date_en_francais(date_iso: str) -> str:
    """« 2026-10-05 » -> « 5 octobre »."""
    jour = datetime.strptime(date_iso, "%Y-%m-%d").date()
    return f"{'1er' if jour.day == 1 else jour.day} {MOIS[jour.month - 1]}"


def build(etape: str, entry: Dict[str, Any], nom_candidat: str) -> Dict[str, str]:
    """Brouillon de relance pour une entrée spontanée : objet « Re: » de l'objet d'origine, corps du modèle de l'étape."""
    if etape not in TEMPLATES:
        raise ValueError(f"Pas de modèle de relance spontanée pour l'étape {etape}.")
    prenom = str(entry.get("prenom") or "").strip()
    corps = TEMPLATES[etape].format(prenom=prenom, date=date_en_francais(entry["date_j0"]),
                                nom=nom_affiche(nom_candidat))
    if not prenom:
        corps = corps.replace("Bonjour ,", "Bonjour,", 1)
    # L'objet reste tel quel : « Re: » et l'objet d'origine doivent correspondre au fil Gmail, espace ordinaire comprise.
    return {"objet": f"Re: {entry.get('objet') or 'Alternance en IA'}", "corps": normaliser_typographie(corps)}
