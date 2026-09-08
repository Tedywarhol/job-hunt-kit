"""Fixtures pytest pour la suite de tests du Job-Hunt Kit."""
import json
import os
import sys
from typing import Any, Dict
import pytest

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)


@pytest.fixture
def dummy_personal() -> Dict[str, Any]:
    return {
        "nom": "Jean DUPONT",
        "titre_pro": "Ingénieur Data Science & IA",
        "email": "jean.dupont@test.fr",
        "telephone": "+33 6 12 34 56 78",
        "localisation": "Lyon (69), France",
        "linkedin": "linkedin.com/in/jean-dupont",
        "github": "github.com/jean-dupont",
        "portfolio": "https://jeandupont.dev",
    }


@pytest.fixture
def dummy_cv_data(dummy_personal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "personal": dummy_personal,
        "badge_titre": "Data Scientist & ML Engineer",
        "profil_resume": "Ingénieur en Data Science spécialisé dans les modèles prédictifs et les LLMs.",
        "competences_cles": [
            "Python (FastAPI, PySpark, Polars, Scikit-learn, PyTorch)",
            "SQL & Dataviz (PostgreSQL, BigQuery, Power BI)",
            "IA & GenAI (RAG, Agents LLM, LangChain, Vector DB)",
            "Cloud & MLOps (Docker, GCP, MLflow, CI/CD)",
        ],
        "variables_defaut": {
            "projets_selection": ["Projet 1", "Projet 2"],
            "projets_max": 2,
        },
        "profiles": {
            "alternance": {
                "titre_defaut": "Alternance Data Science & IA (24 mois)",
                "formation_principale": "Cycle Ingénieur Data Science & IA",
                "target_tags": [
                    {"text": "Rythme 3 sem. entreprise / 3 sem. école"},
                    {"text": "Disponibilité Septembre 2026"},
                ],
            },
            "stage": {
                "titre_defaut": "Stage Data Science & IA (6 mois)",
                "formation_principale": "Cycle Ingénieur Data Science & IA",
                "target_tags": [
                    {"text": "Durée 6 mois"},
                    {"text": "Disponibilité Immédiate"},
                ],
            },
        },
        "experiences": [
            {
                "titre": "Data Scientist",
                "entreprise": "Tech Innov",
                "periode": "2024 - 2025",
                "lieu": "Lyon, France",
                "description": "Déploiement de modèles prédictifs",
                "actions": [
                    "Optimisation d'un pipeline de scoring client (AUC +15%)",
                    "Développement d'APIs FastAPI pour l'inférence temps réel",
                ],
                "bilan": "Traitement de 500k requêtes/jour avec une latence < 50ms",
            }
        ],
        "projets": [
            {
                "titre": "Plateforme RAG Médicale",
                "contexte": "Projet de recherche",
                "role": "Lead Architect",
                "periode": "2025",
                "stack": "Python, LangChain, Qdrant, Streamlit",
                "points": ["Indexation vectorielle de 50k publications"],
                "impact": "✓ Bilan : Réduction du temps de recherche de 80%",
            },
            {
                "titre": "HR Turnover Predictor",
                "contexte": "Projet académique",
                "role": "Data Scientist",
                "periode": "2024",
                "stack": "Scikit-learn, XGBoost, SHAP",
                "points": ["Analyse de sensibilité et explicabilité"],
                "impact": "✓ Bilan : Modèle avec AUC de 0.91",
            },
        ],
    }
