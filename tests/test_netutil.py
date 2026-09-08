"""Tests unitaires pour le retry réseau (N4, scripts/netutil.py)."""
import urllib.error
import unittest.mock as mock

import pytest

from netutil import is_transient, with_retries


def test_is_transient_http_5xx() -> None:
    err = urllib.error.HTTPError("http://x", 503, "Service Unavailable", {}, None)
    assert is_transient(err) is True


def test_is_transient_http_4xx_not_retried() -> None:
    err = urllib.error.HTTPError("http://x", 404, "Not Found", {}, None)
    assert is_transient(err) is False


def test_is_transient_url_error() -> None:
    assert is_transient(urllib.error.URLError("connection refused")) is True


def test_is_transient_other_exception_not_retried() -> None:
    assert is_transient(ValueError("JSON malformé")) is False


def test_with_retries_succeeds_first_try() -> None:
    fn = mock.MagicMock(return_value="ok")
    assert with_retries(fn, attempts=3, base_delay=0) == "ok"
    assert fn.call_count == 1


@mock.patch("netutil.time.sleep")
def test_with_retries_recovers_after_transient_failure(mock_sleep: mock.MagicMock) -> None:
    fn = mock.MagicMock(side_effect=[urllib.error.URLError("timeout"), "ok"])
    assert with_retries(fn, attempts=3, base_delay=1.0) == "ok"
    assert fn.call_count == 2
    mock_sleep.assert_called_once_with(1.0)  # base_delay * 2**0


@mock.patch("netutil.time.sleep")
def test_with_retries_gives_up_after_max_attempts(mock_sleep: mock.MagicMock) -> None:
    fn = mock.MagicMock(side_effect=urllib.error.URLError("toujours en panne"))
    with pytest.raises(urllib.error.URLError):
        with_retries(fn, attempts=3, base_delay=0.01)
    assert fn.call_count == 3


def test_with_retries_does_not_retry_non_transient() -> None:
    fn = mock.MagicMock(side_effect=urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, None))
    with pytest.raises(urllib.error.HTTPError):
        with_retries(fn, attempts=3, base_delay=0.01)
    assert fn.call_count == 1  # pas de tentative supplémentaire sur un 401
