#!/usr/bin/env python3
"""Génère et crée automatiquement des brouillons Gmail ciblés avec CV PDF pour les offres PASS sélectionnées."""
import argparse
import json
import os
import sys

from typing import Any, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from create_gmail_draft import create_draft, get_gmail_service
from profile import doc_base_names, load_personal, ville_from_localisation


def get_focus_text(titre: str) -> str:
    titre_lower = titre.lower()
    if any(k in titre_lower for k in ["data engineer", "pipeline", "etl", "ingénieur données"]):
        return (
            "Mon parcours m'a permis de développer une solide expertise technique en ingénierie de données "
            "(Python, SQL, conception de pipelines ETL automatisés, bases relationnelles et NoSQL) et en modélisation. "
            "Lors de mes précédentes missions, j'ai notamment consolidé des flux de données multi-sources et automatisé "
            "des processus d'alimentation fiables et monitorés."
        )
    if any(k in titre_lower for k in ["datascientist", "data scientist", "statistique", "machine learning"]):
        return (
            "Mon profil allie modélisation statistique, machine learning appliqué (Scikit-learn, XGBoost) et "
            "développement d'architectures d'IA modernes. J'ai notamment développé un modèle prédictif supervisé "
            "avec une AUC de 0,92 dans le secteur de la santé, en intégrant les principes de gouvernance et d'explicabilité."
        )
    if any(k in titre_lower for k in ["ia", "intelligence artificielle", "llm", "genai", "agent"]):
        return (
            "Mon parcours m'a permis de développer une expertise concrète sur les architectures d'IA générative "
            "(RAG de bout en bout, agents LLM, vectorisation sémantique et gardes-fous contre les hallucinations) "
            "ainsi que sur le cadrage et l'industrialisation de cas d'usage IA orientés impact métier."
        )
    return (
        "Mon parcours m'a permis de développer une double compétence en ingénierie logicielle Python, valorisation "
        "des données (SQL, dashboards décisionnels Power BI) et automatisation de processus métiers complexes."
    )


def build_email_body(offer: Dict[str, Any], personal: Optional[Dict[str, Any]] = None) -> str:
    p = personal or load_personal()
    titre: str = offer.get("poste", "Poste")
    ref: str = offer.get("numero_offre") or "N/A"
    admin: str = offer.get("entreprise") or "votre administration"
    focus: str = get_focus_text(titre)

    nom = p.get("nom", "Candidat")
    tel = p.get("telephone", "")
    email = p.get("email", "")
    linkedin = p.get("linkedin_url") or p.get("linkedin", "")
    linkedin_line = f"LinkedIn : {linkedin}\n" if linkedin else ""
    loc = p.get("localisation", "France")
    signature = f"{nom}\n{tel}\n{email}\n{linkedin_line}{loc}".strip()

    return f"""Bonjour Madame, Monsieur,

Je me permets de vous contacter afin de vous soumettre ma candidature pour l'offre d'apprentissage : « {titre} » (Réf. {ref}) au sein de {admin}.

Actuellement étudiant en cycle d'ingénieur spécialisé en Data Science et Intelligence Artificielle à Paris, je recherche une alternance de 24 mois à compter de septembre 2026, au rythme de 3 semaines en organisme pour 3 semaines en formation.

{focus}

Intégrer {admin} représente pour moi l'opportunité idéale de mettre ma rigueur méthodologique, ma curiosité et mes compétences techniques au service de défis structurants d'intérêt public.

Vous trouverez ci-joint mon curriculum vitae détaillant mes réalisations et projets. Je me tiens à votre entière disposition pour tout échange ou entretien.

En vous remerciant pour l'attention portée à ma candidature, je vous prie d'agréer l'expression de mes salutations distinguées.

{signature}"""


def main() -> None:
    personal = load_personal()
    cv_base, _ = doc_base_names(personal)
    default_cv = os.path.join(ROOT, "outputs", f"{cv_base}_Alternance.pdf")

    parser = argparse.ArgumentParser(description="Générer des brouillons Gmail pour les meilleures offres PASS")
    parser.add_argument("--top", type=int, default=5, help="Nombre d'offres top à traiter (défaut: 5)")
    parser.add_argument(
        "--cv",
        default=default_cv,
        help="Chemin vers le CV PDF",
    )
    args = parser.parse_args()

    in_file = os.path.join(ROOT, "state", "pass_alternance_scored.json")
    if not os.path.isfile(in_file):
        sys.exit(f"Fichier manquant : {in_file}. Lancez d'abord le scraping PASS.")

    with open(in_file, "r", encoding="utf-8") as f:
        offers = json.load(f)

    # Filtrer les offres qui ont un email
    valid_offers = [o for o in offers if o.get("contact_recruteur") and "@" in o["contact_recruteur"]]
    selected = valid_offers[:args.top]

    print(f"Connexion au service Gmail pour {personal.get('email', '')}...")
    service = get_gmail_service()

    print(f"\nCréation de {len(selected)} brouillons ciblés dans Gmail avec CV joint...\n")

    created = 0
    for i, o in enumerate(selected, 1):
        to_email = o["contact_recruteur"]
        ref = o.get("numero_offre") or "N/A"
        subject = f"Candidature Alternance (24 mois) — {o['poste']} (Réf. {ref}) — {personal.get('nom', 'Candidat')}"
        body = build_email_body(o, personal)

        try:
            draft = create_draft(service, to_email, subject, body, args.cv, from_email=personal.get("email"))
            draft_id = draft.get("id")
            created += 1
            print(f"[{i}/{len(selected)}] ✅ Brouillon créé (ID: {draft_id})")
            print(f"    - Poste       : {o['poste']}")
            print(f"    - Organisme   : {o['entreprise']}")
            print(f"    - Destinataire: {to_email}\n")
        except Exception as e:
            print(f"[{i}/{len(selected)}] ❌ Erreur sur {o['poste']}: {e}\n")

    print(f"Terminé : {created} brouillons prêts dans votre boîte Gmail (https://mail.google.com/mail/u/0/#drafts) !")


if __name__ == "__main__":
    main()
