"""Tests unitaires pour scripts/create_gmail_draft.py (find_reply, multi-pièces jointes).

find_reply() est la brique de détection de réponse utilisée par le moteur de relances
(run_followups.py) — un faux négatif ici risque de relancer quelqu'un qui a déjà répondu.
Régression couverte : jusqu'au 2026-09-14, une seule adresse était cherchée par candidature,
ratant les réponses envoyées depuis un domaine différent de celui enregistré (cas réel :
administration avec plusieurs domaines @gouv.fr, refus manqué faute de recherche sur la
bonne adresse). Voir aussi email_alias_connue dans state/outreach.json.
"""
from typing import Any, Dict
import unittest.mock as mock

from create_gmail_draft import find_reply


def _service_returning(messages: Any) -> mock.MagicMock:
    service = mock.MagicMock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": messages
    }
    return service


def _last_query(service: mock.MagicMock) -> str:
    _, kwargs = service.users.return_value.messages.return_value.list.call_args
    return kwargs["q"]


def test_find_reply_single_address_query_unchanged() -> None:
    """Comportement historique préservé : une seule adresse -> pas de clause OR/parenthèses."""
    service = _service_returning([])
    find_reply(service, "recruteur@exemple.fr", "2026-09-01")
    assert _last_query(service) == "from:recruteur@exemple.fr after:2026/09/01"


def test_find_reply_no_match_returns_none() -> None:
    service = _service_returning([])
    assert find_reply(service, "recruteur@exemple.fr", "2026-09-01") is None


def test_find_reply_single_address_found() -> None:
    service = _service_returning([{"threadId": "thread-1"}])
    assert find_reply(service, "recruteur@exemple.fr", "2026-09-01") == "thread-1"


def test_find_reply_multi_address_builds_or_query() -> None:
    service = _service_returning([])
    find_reply(service, ["a@exemple.fr", "b@exemple.fr"], "2026-09-01")
    assert _last_query(service) == "(from:a@exemple.fr OR from:b@exemple.fr) after:2026/09/01"


def test_find_reply_finds_reply_on_alias_address() -> None:
    """Cas réel du 2026-09-14 : la réponse arrive depuis l'adresse alias, pas l'adresse
    enregistrée en premier — une seule requête Gmail (clause OR) doit quand même la trouver."""
    service = _service_returning([{"threadId": "thread-alias"}])
    thread_id = find_reply(
        service,
        ["nolwenn.jezequel@mer.gouv.fr", "nolwenn.jezequel@developpement-durable.gouv.fr"],
        "2026-09-01",
    )
    assert thread_id == "thread-alias"


def test_find_reply_empty_list_returns_none_without_api_call() -> None:
    service = _service_returning([{"threadId": "would-not-be-seen"}])
    assert find_reply(service, [], "2026-09-01") is None
    service.users.return_value.messages.return_value.list.assert_not_called()


def test_find_reply_filters_out_falsy_addresses() -> None:
    """entry.get('email_alias_connue') est souvent None -> ne doit jamais produire
    une clause 'from:None' dans la requête Gmail."""
    service = _service_returning([])
    find_reply(service, ["recruteur@exemple.fr", None], "2026-09-01")  # type: ignore[list-item]
    assert _last_query(service) == "from:recruteur@exemple.fr after:2026/09/01"
