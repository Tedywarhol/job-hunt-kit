#!/usr/bin/env python3
"""Fallback de scrape stealth (Scrapling) pour le job-scout, quand Apify/Firecrawl bloquent.

Usage:
  python scripts/scrape_scrapling.py <url> [--stealth] [--selector "CSS"] [--timeout-ms 30000]

- Sans --stealth : Fetcher HTTP rapide (curl_cffi), suffisant pour la plupart des pages.
- Avec --stealth : StealthyFetcher (navigateur patchright) pour les sites anti-bot / JS.

ATTENTION : le timeout de Scrapling est en MILLISECONDES (pas en secondes).
Sort le texte extrait (ou la page) sur stdout, en JSON.
"""
import argparse
import json
from typing import Any, Dict, List, Optional


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--stealth", action="store_true")
    ap.add_argument("--selector", default=None, help="Sélecteur CSS optionnel (ex: 'h1::text').")
    ap.add_argument("--timeout-ms", type=int, default=30000, help="Timeout en millisecondes.")
    args = ap.parse_args()

    from scrapling.fetchers import Fetcher, StealthyFetcher

    if args.stealth:
        r = StealthyFetcher.fetch(args.url, timeout=args.timeout_ms, headless=True)
    else:
        # Fetcher.get attend un timeout en secondes.
        r = Fetcher.get(args.url, timeout=max(1, args.timeout_ms // 1000), stealthy_headers=True)

    out: Dict[str, Any] = {"url": args.url, "status": getattr(r, "status", None), "stealth": args.stealth}
    if args.selector:
        try:
            sel = r.css(args.selector)
            out["matches"] = [str(x) for x in sel]
        except Exception as e:
            out["selector_error"] = str(e)
    else:
        try:
            out["text"] = r.get_all_text()[:20000]
        except Exception:
            out["html_len"] = len(getattr(r, "html_content", "") or "")

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
