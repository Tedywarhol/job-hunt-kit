#!/usr/bin/env python3
"""Retry réseau minimal avec backoff exponentiel (N4, docs/plans/2026-09-07-plan-amelioration.md).

Ne retente JAMAIS une erreur non transitoire (ex. 401/404 Notion, JSON malformé côté
serveur) : retenter un token invalide ne le rend pas valide, ça masque juste l'échec plus
longtemps derrière un délai inutile. Ne retente que : timeouts, erreurs de connexion
(DNS, réseau) et statuts HTTP >= 500 (erreur serveur, potentiellement transitoire).
"""
import time
import urllib.error
from typing import Callable, TypeVar

T = TypeVar("T")


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    if isinstance(exc, urllib.error.URLError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    return False


def with_retries(fn: Callable[[], T], attempts: int = 3, base_delay: float = 1.0) -> T:
    """Exécute fn() avec jusqu'à `attempts` tentatives. Backoff exponentiel
    (base_delay, base_delay*2, ...) entre chaque tentative transitoire. Relance
    immédiatement sur une erreur jugée non transitoire (voir is_transient), et relance
    la dernière exception si toutes les tentatives transitoires sont épuisées."""
    last_exc: BaseException = RuntimeError("with_retries: aucune tentative exécutée")
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < attempts - 1 and is_transient(e):
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise
    raise last_exc
