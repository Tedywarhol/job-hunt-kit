"""Tests unitaires pour les moteurs de rendu HTML et PDF."""
import os
from typing import Any, Dict
import unittest.mock as mock

from render_cv import (
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
