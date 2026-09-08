#!/usr/bin/env python3
"""Logging minimal des erreurs non-fatales : aucun `except: pass` silencieux.

Toute exception rattrapée qui n'est pas déjà imprimée/remontée doit passer par
`log_error()` — visible sur stderr immédiatement, et tracée dans
`logs/errors.log` pour rester consultable même en usage non-interactif
(routine planifiée, CLI sans terminal attaché).
"""
from datetime import datetime
import os
import sys

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE: str = os.path.join(ROOT, "logs", "errors.log")


def log_error(context: str, exc: BaseException) -> None:
    """Trace une erreur non-fatale (stderr + logs/errors.log). Ne lève jamais elle-même."""
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {context}: {exc!r}"
    print(f"[warn] {line}", file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # le logging est best-effort : il ne doit jamais faire planter l'appelant
