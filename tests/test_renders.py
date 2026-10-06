"""Tests unitaires pour les moteurs de rendu HTML et PDF."""
import os
from typing import Any, Dict
import unittest.mock as mock

import pytest

from render_cv import (
    badge_etudiant,
    build_html as build_cv_html,
    esc,
    find_chrome,
    order_competences,
    select_projets,
)
from render_lettre import (
    build_html as build_lettre_html,
    build_paragraphs_html,
)


def test_esc() -> None:
    assert esc('<div class="test">& "quote"</div>') == '&lt;div class=&quot;test&quot;&gt;&amp; &quot;quote&quot;&lt;/div&gt;'


def test_order_competences() -> None:
    items = [
        "Python (FastAPI, PySpark)",
        "SQL (PostgreSQL, BigQuery)",
        "IA & GenAI (RAG, Agents)",
        "Cloud (Docker, GCP)",
    ]
    keywords = ["ia", "cloud"]
    ordered = order_competences(items, keywords)
    assert len(ordered) == 4
    # "IA & GenAI" et "Cloud" doivent passer en tête
    assert "IA & GenAI" in ordered[0] or "Cloud" in ordered[0]


def test_select_projets(dummy_cv_data: Dict[str, Any]) -> None:
    projets = dummy_cv_data["projets"]
    selected = select_projets(projets, selection=["HR Turnover Predictor"], projets_max=1)
    assert len(selected) == 1
    assert selected[0]["titre"] == "HR Turnover Predictor"


def test_build_cv_html(dummy_cv_data: Dict[str, Any]) -> None:
    vars_data: Dict[str, Any] = {
        "titre": "Alternance Data Engineer",
        "accroche": "Profil ciblé pour l'ingénierie des données",
        "mots_cles_ats": ["Kafka", "Airflow", "PySpark"],
    }
    html = build_cv_html(dummy_cv_data, vars_data, profile="alternance")
    assert "<!DOCTYPE html>" in html
    assert "Jean DUPONT" in html
    assert "Alternance Data Engineer" in html
    assert esc("Profil ciblé pour l'ingénierie des données") in html
    assert "ats-hidden-layer" in html
    assert "Kafka" in html


def test_cv_ne_contient_aucun_tiret_cadratin(dummy_cv_data: Dict[str, Any]) -> None:
    """Règle du projet, rappelée le 2026-10-03 : jamais « — » sur un CV, ni dans les titres de projets,
    ni dans la ligne des langues, ni dans l'accroche."""
    dummy_cv_data["projets"][0]["titre"] = "Plateforme RAG — Médicale"
    dummy_cv_data["langues"] = [{"langue": "Anglais", "niveau": "Intermédiaire professionnel (B2)"}]
    html = build_cv_html(dummy_cv_data, {"accroche": "Étudiant ingénieur — data et IA"}, profile="alternance")
    assert "—" not in html
    assert "Plateforme RAG : Médicale" in html
    assert 'Anglais <span>· Intermédiaire professionnel (B2)</span>' in html


def test_experience_affiche_le_type_de_contrat(dummy_cv_data: Dict[str, Any]) -> None:
    """Retour du 2026-10-03 : les expériences étaient des stages et « ça ne se voyait nulle part »."""
    dummy_cv_data["experiences"][0]["contrat"] = "Stage"
    html = build_cv_html(dummy_cv_data, {}, profile="alternance")
    assert '<strong class="contrat">Stage</strong> · Tech Innov' in html
    dummy_cv_data["experiences"][0].pop("contrat")
    assert '<strong class="contrat">' not in build_cv_html(dummy_cv_data, {}, profile="alternance")


@pytest.mark.parametrize("badge,attendu", [
    ("Ingénieur Data & IA", "Étudiant ingénieur\nData & IA"),
    ("Ingénieur Data Science & IA", "Étudiant ingénieur\nData Science & IA"),
    ("Ingénieur & Communication", "Étudiant ingénieur\nCommunication"),
    ("ingénieur", "Étudiant ingénieur"),
    ("Étudiant ingénieur\nData Science & IA", "Étudiant ingénieur\nData Science & IA"),
    ("Data Science & IA", "Data Science & IA"),
])
def test_badge_etudiant(badge: str, attendu: str) -> None:
    """Un étudiant n'est pas encore ingénieur : le titre sous le nom ne doit jamais l'affirmer."""
    assert badge_etudiant(badge) == attendu


def test_le_titre_sous_le_nom_est_corrige_meme_si_l_offre_ecrit_ingenieur(dummy_cv_data: Dict[str, Any]) -> None:
    html = build_cv_html(dummy_cv_data, {"badge_titre": "Ingénieur Data & IA"}, profile="alternance")
    assert '<div class="badge-title">Étudiant ingénieur<br>Data &amp; IA</div>' in html


def test_select_projets_retrouve_un_titre_ecrit_avec_un_tiret_cadratin() -> None:
    """Les anciens cv-vars écrivent « A — B » alors que le CV maître écrit maintenant « A : B »."""
    projets = [{"titre": "Autre projet"}, {"titre": "HR Analytics : Modélisation prédictive du turnover"}]
    choisis = select_projets(projets, selection=["HR Analytics — Modélisation prédictive du turnover"], projets_max=1)
    assert [p["titre"] for p in choisis] == ["HR Analytics : Modélisation prédictive du turnover"]


def test_build_lettre_html(dummy_cv_data: Dict[str, Any]) -> None:
    vars_data: Dict[str, Any] = {
        "poste": "Ingénieur IA & Data",
        "entreprise": "Direction Numérique de l'État",
        "destinataire": "Madame la Directrice",
        "objet": "Candidature Alternance 24 mois",
        "paragraphes": [
            {"texte": "Premier paragraphe d'introduction."},
            {"texte": "Second paragraphe détaillant les compétences.", "points": ["Point A", "Point B"]},
        ],
    }
    html = build_lettre_html(dummy_cv_data, vars_data)
    assert "<!DOCTYPE html>" in html
    assert "Jean DUPONT" in html
    assert esc("Direction Numérique de l'État") in html
    assert "Madame la Directrice" in html
    assert "Candidature Alternance 24 mois" in html
    assert esc("Premier paragraphe d'introduction.") in html
    assert "Point A" in html


def test_find_chrome() -> None:
    chrome = find_chrome()
    # Sur l'environnement de test, Chrome ou Edge doit être détecté
    assert chrome is not None
    assert "exe" in chrome.lower()


def test_find_chrome_env_var_takes_priority() -> None:
    """CHROME_PATH doit toujours l'emporter, quel que soit l'OS."""
    with mock.patch.dict(os.environ, {"CHROME_PATH": "/chemin/perso/chrome"}):
        with mock.patch("os.path.isfile", side_effect=lambda p: p == "/chemin/perso/chrome"):
            assert find_chrome() == "/chemin/perso/chrome"


def test_find_chrome_checks_macos_paths() -> None:
    """Régression 2026-09-08 : find_chrome ne couvrait que des chemins Windows en dur —
    sur macOS/Linux frais, rien n'était détecté sans CHROME_PATH déjà connu."""
    mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CHROME_PATH", None)
        with mock.patch("sys.platform", "darwin"):
            with mock.patch("os.path.isfile", side_effect=lambda p: p == mac_path):
                assert find_chrome() == mac_path


def test_find_chrome_checks_linux_paths() -> None:
    linux_path = "/usr/bin/google-chrome"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CHROME_PATH", None)
        with mock.patch("sys.platform", "linux"):
            with mock.patch("os.path.isfile", side_effect=lambda p: p == linux_path):
                assert find_chrome() == linux_path
