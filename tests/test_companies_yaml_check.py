"""Tests unitaires pour le diagnostic config/companies.yaml (scripts/check_companies_yaml.py)."""
import unittest.mock as mock

from check_companies_yaml import check_company, endpoint_for


def test_endpoint_for_greenhouse() -> None:
    comp = {"nom": "Dataiku", "ats": "greenhouse", "careers_url": "https://boards.greenhouse.io/dataiku"}
    assert endpoint_for(comp) == "https://boards-api.greenhouse.io/v1/boards/dataiku/jobs"


def test_endpoint_for_lever() -> None:
    comp = {"nom": "Mirakl", "ats": "lever", "careers_url": "https://jobs.lever.co/mirakl"}
    assert endpoint_for(comp) == "https://api.lever.co/v0/postings/mirakl?mode=json"


def test_endpoint_for_ashby() -> None:
    comp = {"nom": "Mistral AI", "ats": "ashby", "careers_url": "https://jobs.ashbyhq.com/mistral"}
    assert endpoint_for(comp) == "https://api.ashbyhq.com/posting-api/job-board/mistral"


def test_endpoint_for_non_api_source_returns_none() -> None:
    comp = {"nom": "ChapsVision", "ats": "autre", "careers_url": "https://www.chapsvision.fr/carrieres/"}
    assert endpoint_for(comp) is None


@mock.patch("check_companies_yaml.fetch_json")
def test_check_company_ok(mock_fetch: mock.MagicMock) -> None:
    mock_fetch.return_value = {"jobs": []}
    comp = {"nom": "Dataiku", "ats": "greenhouse", "careers_url": "https://boards.greenhouse.io/dataiku"}
    assert check_company(comp)["statut"] == "OK"


@mock.patch("check_companies_yaml.fetch_json")
def test_check_company_broken(mock_fetch: mock.MagicMock) -> None:
    mock_fetch.return_value = None
    comp = {"nom": "Alan", "ats": "greenhouse", "careers_url": "https://boards.greenhouse.io/alan"}
    assert check_company(comp)["statut"] == "BROKEN"


def test_check_company_non_api_source() -> None:
    comp = {"nom": "ChapsVision", "ats": "autre", "careers_url": "https://www.chapsvision.fr/carrieres/"}
    assert check_company(comp)["statut"] == "non-api"
