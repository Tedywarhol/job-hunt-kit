"""Tests unitaires pour les connecteurs API ATS (Greenhouse, Lever, Ashby)."""
from datetime import date, timedelta
from typing import Any, Dict, List
import unittest.mock as mock

from scrape_ats_api import (
    is_job_relevant,
    parse_ashby,
    parse_greenhouse,
    parse_lever,
    update_pending_upsert,
)


def test_is_job_relevant() -> None:
    # Cas positifs
    assert is_job_relevant("Data Scientist / ML Engineer", "Paris, France")
    assert is_job_relevant("Ingénieur IA & NLP", "Remote - France")
    assert is_job_relevant("Python Backend Developer", "Île-de-France")
    assert is_job_relevant("Consultant Big Data & BI", "")

    # Cas négatifs (hors domaine)
    assert not is_job_relevant("Office Manager", "Paris")
    assert not is_job_relevant("Comptable Général", "Paris")
    # Cas négatifs (hors zone géographique autorisée)
    assert not is_job_relevant("Data Scientist", "Tokyo, Japan")


def test_is_job_relevant_excludes_off_scope_functions() -> None:
    """Fusion M0 (2026-09-07) : une fonction métier hors data/IA/tech est exclue même si
    le titre contient un mot-clé KEYWORDS_RELEVANCE par coïncidence (ex. 'Data' dans DPO)."""
    assert not is_job_relevant("Data Privacy Officer / DPO", "Paris")
    assert not is_job_relevant("Growth Data Analyst", "Paris")
    assert not is_job_relevant("Content Strategist IA", "Paris")


def test_is_job_relevant_excludes_foreign_language_requirement() -> None:
    """Fusion M0 : une offre exigeant une langue étrangère hors FR/EN est exclue."""
    assert not is_job_relevant("Data Analyst - German speaker required", "Paris")


def test_is_job_relevant_extended_location_list() -> None:
    """Fusion M0 : la liste de localisations françaises a été élargie (villes/banlieues IDF)."""
    assert is_job_relevant("Data Engineer", "Strasbourg")
    assert is_job_relevant("Data Analyst", "Nanterre (92)")


@mock.patch("scrape_ats_api.fetch_json")
def test_parse_greenhouse(mock_fetch: mock.MagicMock) -> None:
    mock_fetch.return_value = {
        "jobs": [
            {
                "id": 101,
                "title": "Machine Learning Engineer - Alternance",
                "absolute_url": "https://boards.greenhouse.io/dataiku/jobs/101",
                "location": {"name": "Paris, France"},
            },
            {
                "id": 102,
                "title": "HR Business Partner",
                "absolute_url": "https://boards.greenhouse.io/dataiku/jobs/102",
                "location": {"name": "Paris, France"},
            },
        ]
    }
    jobs = parse_greenhouse("dataiku", "Dataiku")
    assert len(jobs) == 1
    assert jobs[0]["entreprise"] == "Dataiku"
    assert jobs[0]["poste"] == "Machine Learning Engineer - Alternance"
    assert jobs[0]["type"] == "alternance"
    assert jobs[0]["source"] == "Greenhouse"


@mock.patch("scrape_ats_api.fetch_json")
def test_parse_lever(mock_fetch: mock.MagicMock) -> None:
    mock_fetch.return_value = [
        {
            "id": "lev-1",
            "text": "Data Analyst Intern (Stage 6 mois)",
            "hostedUrl": "https://jobs.lever.co/mirakl/lev-1",
            "categories": {"location": "Paris, France"},
        }
    ]
    jobs = parse_lever("mirakl", "Mirakl")
    assert len(jobs) == 1
    assert jobs[0]["entreprise"] == "Mirakl"
    assert jobs[0]["type"] == "stage"
    assert jobs[0]["source"] == "Lever"


@mock.patch("scrape_ats_api.fetch_json")
def test_parse_ashby(mock_fetch: mock.MagicMock) -> None:
    mock_fetch.return_value = {
        "jobs": [
            {
                "id": "ash-1",
                "title": "AI Research Engineer",
                "jobUrl": "https://jobs.ashbyhq.com/mistral/ash-1",
                "location": "Paris, France",
            }
        ]
    }
    jobs = parse_ashby("mistral", "Mistral AI")
    assert len(jobs) == 1
    assert jobs[0]["entreprise"] == "Mistral AI"
    assert jobs[0]["source"] == "Ashby"


def test_normalize_date_scenarios() -> None:
    from scrape_ats_api import normalize_date
    from datetime import date

    today_str = date.today().isoformat()

    # None or empty -> date du jour, age 0
    d, age = normalize_date(None)
    assert d == today_str
    assert age == 0

    d, age = normalize_date("")
    assert d == today_str
    assert age == 0

    # Timestamp Unix en millisecondes (ex: 1725192000000 -> 2024-09-01)
    d, age = normalize_date(1725192000000)
    assert len(d) == 10
    assert "-" in d

    # String ISO
    d, age = normalize_date("2026-08-20T10:00:00Z")
    assert d == "2026-08-20"
    assert age >= 0

    # Date FR
    d, age = normalize_date("20/08/2026")
    assert d == "2026-08-20"


def test_calculate_recency_score() -> None:
    from scrape_ats_api import calculate_recency_score

    # Très récent (aujourd'hui / 1 jour) -> +15 pts
    assert calculate_recency_score(70, 0) == 85
    assert calculate_recency_score(70, 1) == 85

    # Moins de 7 jours -> +10 pts
    assert calculate_recency_score(70, 5) == 80

    # Moins de 14 jours -> +5 pts
    assert calculate_recency_score(70, 10) == 75

    # Ancien (> 45 jours) -> -15 pts
    assert calculate_recency_score(70, 50) == 55


def test_score_pass_offer() -> None:
    from filter_alternance_pass import score_pass_offer

    # Date relative à "aujourd'hui" (pas une date figée) : une chaîne codée en dur
    # devient périmée dès que le nombre de jours réels écoulés dépasse le seuil testé
    # (constaté : "2026-08-30" a fait échouer ce test 15 jours plus tard, alors que
    # le code lui-même n'avait pas régressé).
    recent_date = date.today() - timedelta(days=3)
    offer = {
        "titre": "Chef de projet IA et Data Science",
        "description_poste": "Développement de pipelines Python et modèles de Machine Learning.",
        "profil_recherche": "Maîtrise de SQL et Power BI.",
        "duree_contrat": "24 mois",
        "date_publication": recent_date.isoformat(),
    }
    score, notes, is_24, date_iso, age_days = score_pass_offer(offer)
    assert score >= 85
    assert is_24 is True
    assert date_iso == recent_date.isoformat()
    assert age_days <= 10

