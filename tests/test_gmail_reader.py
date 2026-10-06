"""Tests du lecteur Gmail robuste (scripts/gmail_reader.py) : quota, reprise, cache. Aucun appel réel."""
from typing import Any, Dict
import unittest.mock as mock

import pytest
from googleapiclient.errors import HttpError

import gmail_reader
from gmail_reader import GmailReader, execute


def http_error(status: int) -> HttpError:
    return HttpError(resp=mock.Mock(status=status, reason="quota"), content=b"{}")


def test_execute_retries_on_quota_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gmail_reader.time, "sleep", lambda _s: None)
    request = mock.Mock()
    request.execute.side_effect = [http_error(403), http_error(429), {"ok": True}]
    assert execute(request) == {"ok": True}
    assert request.execute.call_count == 3


def test_execute_does_not_retry_a_real_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gmail_reader.time, "sleep", lambda _s: None)
    request = mock.Mock()
    request.execute.side_effect = http_error(404)
    with pytest.raises(HttpError):
        execute(request)
    assert request.execute.call_count == 1


def _message(msg_id: str) -> Dict[str, Any]:
    return {"id": msg_id, "threadId": "t1", "internalDate": "1790000000000",
            "payload": {"headers": [{"name": "From", "value": "A <a@b.fr>"}, {"name": "Subject", "value": "Candidature"}]}}


def test_headers_are_read_once_and_survive_a_restart(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gmail_reader.time, "sleep", lambda _s: None)
    service = mock.MagicMock()
    service.users().messages().get().execute.return_value = _message("m1")
    cache = str(tmp_path / "cache.json")
    reader = GmailReader(service, cache)
    first = reader.headers("m1")
    reader.headers("m1")
    reader.save()
    assert first["from"] == "A <a@b.fr>" and first["thread"] == "t1"
    assert service.users().messages().get().execute.call_count == 1
    restarted = GmailReader(mock.MagicMock(), cache)
    assert restarted.headers("m1") == first  # lu depuis le cache, sans appel
