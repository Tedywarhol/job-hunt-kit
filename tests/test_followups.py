"""Tests unitaires pour le moteur de relances (scripts/run_followups.py).

Aucun test ici ne touche l'API Gmail ou Notion réelle : find_reply/create_draft
sont mockés. C'est la zone identifiée comme la plus sensible dans l'audit du
2026-09-07 (elle peut envoyer des emails réels une fois --apply et un futur
mode d'envoi activés) — elle doit être la mieux couverte.
"""
from datetime import date, timedelta
from typing import Any, Dict
import unittest.mock as mock

from run_followups import (
    anchor_plus,
    build_relance,
    days_since,
    next_step,
    process_entry,
)


def _entry(etape: str = "J+0", jours_ecoules: int = 0, **overrides: Any) -> Dict[str, Any]:
    anchor = (date.today() - timedelta(days=jours_ecoules)).isoformat()
    base: Dict[str, Any] = {
        "email": "recruteur@exemple.fr",
        "entreprise": "Exemple Corp",
        "poste": "Data Scientist",
        "etape": etape,
        "date_creation_brouillon": anchor,
    }
    base.update(overrides)
    return base


def test_next_step_sequence() -> None:
    assert next_step("J+0") == "J+3"
    assert next_step("J+3") == "J+5"
    assert next_step("J+7") == "J+10"
    assert next_step("J+10") is None
    assert next_step("Terminé") is None
    assert next_step("Réponse reçue") is None


def test_days_since_and_anchor_plus() -> None:
    anchor = (date.today() - timedelta(days=5)).isoformat()
    assert days_since(anchor) == 5
    assert anchor_plus(anchor, 3) == (date.today() - timedelta(days=2)).isoformat()


def test_build_relance_no_forbidden_chars() -> None:
    for etape in ["J+3", "J+5", "J+7", "J+10"]:
        r = build_relance(etape, "Exemple Corp", "Data Scientist", "Jean Dupont")
        assert "Data Scientist" in r["objet"]
        # Règle projet : jamais de tiret cadratin ni de "&" dans le contenu généré.
        assert "—" not in r["corps"]
        assert "&" not in r["corps"]


@mock.patch("run_followups.find_reply")
def test_process_entry_not_due_yet(mock_find_reply: mock.MagicMock) -> None:
    mock_find_reply.return_value = None
    entry = _entry(etape="J+0", jours_ecoules=1)  # J+3 dû dans 2 jours
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "aucune"
    assert "échéance J+3" in result["detail"]
    assert entry["etape"] == "J+0"  # inchangé


@mock.patch("run_followups.create_draft")
@mock.patch("run_followups.find_reply")
def test_process_entry_creates_draft_when_due(mock_find_reply: mock.MagicMock, mock_create_draft: mock.MagicMock) -> None:
    mock_find_reply.return_value = None
    mock_create_draft.return_value = {"id": "draft-123"}
    entry = _entry(etape="J+0", jours_ecoules=3)  # J+3 échu
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "brouillon J+3 créé"
    assert entry["etape"] == "J+3"
    assert entry["statut"] == "Brouillon créé"
    assert entry["brouillon_id"] == "draft-123"
    assert entry["relances"][-1]["etape"] == "J+3"
    mock_create_draft.assert_called_once()


@mock.patch("run_followups.create_draft")
@mock.patch("run_followups.find_reply")
def test_process_entry_dry_run_does_not_mutate(mock_find_reply: mock.MagicMock, mock_create_draft: mock.MagicMock) -> None:
    mock_find_reply.return_value = None
    entry = _entry(etape="J+0", jours_ecoules=3)
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=False)
    assert "préparerait un brouillon J+3" in result["action"]
    assert entry["etape"] == "J+0"  # rien n'est écrit en dry-run
    mock_create_draft.assert_not_called()


@mock.patch("run_followups.create_draft")
@mock.patch("run_followups.find_reply")
def test_process_entry_stops_on_reply(mock_find_reply: mock.MagicMock, mock_create_draft: mock.MagicMock) -> None:
    mock_find_reply.return_value = "thread-abc"
    entry = _entry(etape="J+3", jours_ecoules=10)  # J+5/J+7 seraient dus, mais réponse prioritaire
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "réponse détectée"
    assert entry["etape"] == "Réponse reçue"
    mock_create_draft.assert_not_called()


@mock.patch("run_followups.log_error")
@mock.patch("run_followups.find_reply")
def test_process_entry_gmail_failure_is_never_silent(mock_find_reply: mock.MagicMock, mock_log_error: mock.MagicMock) -> None:
    mock_find_reply.side_effect = Exception("boom: API indisponible")
    entry = _entry(etape="J+3", jours_ecoules=10)
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "ignorée"
    assert "échec" in result["detail"]
    assert entry["etape"] == "J+3"  # rien n'est avancé sur un échec de vérification
    mock_log_error.assert_called_once()  # l'échec est tracé (logs/errors.log), jamais silencieux


@mock.patch("run_followups.find_reply")
def test_process_entry_passes_known_alias_to_find_reply(mock_find_reply: mock.MagicMock) -> None:
    """Régression 2026-09-14 : quand email_alias_connue est renseignée, elle doit être
    cherchée en plus de l'adresse enregistrée (cf. tests/test_create_gmail_draft.py)."""
    mock_find_reply.return_value = None
    entry = _entry(
        etape="J+0", jours_ecoules=1,
        email="nolwenn.jezequel@mer.gouv.fr",
        email_alias_connue="nolwenn.jezequel@developpement-durable.gouv.fr",
    )
    process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    emails_checked = mock_find_reply.call_args[0][1]
    assert set(emails_checked) == {
        "nolwenn.jezequel@mer.gouv.fr",
        "nolwenn.jezequel@developpement-durable.gouv.fr",
    }


@mock.patch("run_followups.find_reply")
def test_process_entry_without_alias_checks_single_email(mock_find_reply: mock.MagicMock) -> None:
    """Cas nominal (pas d'alias connu) : pas de régression, une seule adresse cherchée."""
    mock_find_reply.return_value = None
    entry = _entry(etape="J+0", jours_ecoules=1)  # pas de email_alias_connue
    process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert mock_find_reply.call_args[0][1] == ["recruteur@exemple.fr"]


@mock.patch("run_followups.find_reply")
def test_process_entry_closes_after_j10(mock_find_reply: mock.MagicMock) -> None:
    mock_find_reply.return_value = None
    entry = _entry(etape="J+10", jours_ecoules=20)
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "clôturée"
    assert entry["etape"] == "Terminé"


def test_process_entry_terminal_etape_is_noop() -> None:
    entry = _entry(etape="Réponse reçue")
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "aucune"
    assert "close" in result["detail"]


def test_process_entry_missing_fields_is_ignored() -> None:
    entry = {"entreprise": "Exemple Corp", "poste": "Data Scientist", "etape": "J+0"}  # pas d'email/date
    result = process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=True)
    assert result["action"] == "ignorée"
