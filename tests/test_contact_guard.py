"""Tests du garde-fou avant envoi (scripts/contact_guard.py) et de son branchement dans les relances.

Les phrases viennent de vrais mails reçus (refus, mais aussi accusés de réception et transmissions
aux RH, qui ne sont PAS des refus). Aucun appel Gmail ou Notion réel.
"""
from datetime import date, timedelta
from typing import Dict, List
import unittest.mock as mock

import pytest

from contact_guard import add_refusal, check, is_refusal, load_refusals, save_refusals
from run_followups import process_entry


@pytest.mark.parametrize("snippet", [
    "Je n'ai malheureusement de poste à vous proposer. Bonne chance dans votre recherche",
    "nous sommes au regret de ne pas pouvoir lui réserver une suite favorable",
    "Tous nos postes en alternance sont pourvus à ce jour.",
    "Nous ne prenons pas d'alternance dans notre équipe, je suis désolé",
    "Nous avons toutefois retenu une autre candidature pour ce poste.",
    "Not good luck I'm afraid. We've discussed at length",
])
def test_is_refusal_recognises_real_refusals(snippet: str) -> None:
    assert is_refusal(snippet)


@pytest.mark.parametrize("snippet", [
    "Nous avons bien reçu votre candidature et nous l'étudierons avec attention.",
    "J'ai bien transmis votre CV aux RH.",
    "As far as I've understood, HR department has started the process",
    "Nous revenons vers toi aujourd'hui avec notre réponse.",
    "Je n&#39;en ai malheureusement pris connaissance qu&#39;à mon retour de congé. Votre profil est particulièrement intéressant",
])
def test_is_refusal_ignores_acknowledgements(snippet: str) -> None:
    assert not is_refusal(snippet)


@pytest.fixture
def refusals() -> Dict[str, List[Dict[str, str]]]:
    data: Dict[str, List[Dict[str, str]]] = {}
    add_refusal(data, "Paul.Dubois@conseil-exemple.com", (date.today() - timedelta(days=28)).isoformat(), "gmail", "pas de poste ouvert pour une alternance")
    add_refusal(data, "ancien.manager@acme-aero.com", (date.today() - timedelta(days=140)).isoformat(), "gmail", "pas de poste dans mon périmètre")
    add_refusal(data, "laura.blanc@conseil.teamtailor-mail.com", "2026-10-02", "gmail", "au regret")
    add_refusal(data, "ami@gmail.com", "2026-09-01", "gmail", "malheureusement")
    return data


def test_same_address_is_blocked(refusals: Dict[str, List[Dict[str, str]]]) -> None:
    verdict = check("paul.dubois@conseil-exemple.com", refusals)
    assert verdict is not None and verdict["niveau"] == "bloqué"
    assert (date.today() - timedelta(days=28)).isoformat() in verdict["raison"]


def test_same_company_is_a_warning(refusals: Dict[str, List[Dict[str, str]]]) -> None:
    verdict = check("nadia.roux@conseil-exemple.com", refusals)
    assert verdict is not None and verdict["niveau"] == "attention"
    assert "paul.dubois@conseil-exemple.com" in verdict["raison"]


def test_shared_domains_only_match_the_exact_address(refusals: Dict[str, List[Dict[str, str]]]) -> None:
    assert check("autre.personne@gmail.com", refusals) is None
    assert check("quelquun@autre.teamtailor-mail.com", refusals) is None
    assert check("ami@gmail.com", refusals) is not None


def test_an_old_refusal_by_someone_else_does_not_block_the_company(refusals: Dict[str, List[Dict[str, str]]]) -> None:
    assert check("marie.durand@acme-aero.com", refusals) is None
    assert check("ancien.manager@acme-aero.com", refusals) is not None  # la personne elle-même reste bloquée


def test_extracts_are_stored_readable() -> None:
    data: Dict[str, List[Dict[str, str]]] = {}
    add_refusal(data, "a@b.fr", "2026-10-01", "gmail", "Je n&#39;ai pas de poste")
    assert data["a@b.fr"][0]["extrait"] == "Je n'ai pas de poste"


def test_unknown_company_is_ok(refusals: Dict[str, List[Dict[str, str]]]) -> None:
    assert check("recruteur@exemple.fr", refusals) is None


def test_duplicate_refusals_are_stored_once() -> None:
    data: Dict[str, List[Dict[str, str]]] = {}
    add_refusal(data, "a@b.fr", "2026-10-01", "gmail", "non")
    add_refusal(data, "A@B.fr", "2026-10-01", "gmail", "non")
    assert data == {"a@b.fr": [{"date": "2026-10-01", "source": "gmail", "extrait": "non"}]}


def test_save_and_load_roundtrip(tmp_path, refusals: Dict[str, List[Dict[str, str]]]) -> None:
    path = str(tmp_path / "refus.json")
    save_refusals(refusals, path)
    assert load_refusals(path) == refusals
    assert load_refusals(str(tmp_path / "absent.json")) == {}


@mock.patch("run_followups.create_draft")
@mock.patch("run_followups.find_reply", return_value=None)
def test_followup_is_skipped_when_the_company_refused(
    mock_find_reply: mock.MagicMock, mock_create_draft: mock.MagicMock, refusals: Dict[str, List[Dict[str, str]]],
) -> None:
    anchor = (date.today() - timedelta(days=4)).isoformat()
    entry = {"email": "nadia.roux@conseil-exemple.com", "entreprise": "Conseil Exemple", "poste": "Alternance Data",
             "etape": "J+0", "date_creation_brouillon": anchor}
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True, refusals=refusals)
    assert result["action"] == "ignorée"
    assert "garde-fou" in result["detail"]
    mock_create_draft.assert_not_called()
    assert entry["etape"] == "J+0"
