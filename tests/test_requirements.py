"""Vérifie que requirements.txt déclare tout ce dont le code a réellement besoin.

Découverte du 2026-09-08 : `scrapling>=0.2.0` était présent, mais `scrapling.fetchers`
(utilisé par scrape_pass.py, enrich_pass_offers.py, scrape_scrapling.py) a besoin de
l'extra [fetchers] (curl_cffi, patchright, playwright) — absent d'un `pip install`
nu. Invisible en local car ces paquets avaient été installés à la main à part ;
aurait cassé sur une machine neuve recevant le kit partagé.
"""
import os
import re

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_requirements() -> str:
    with open(os.path.join(ROOT, "requirements.txt"), "r", encoding="utf-8") as f:
        return f.read()


def test_scrapling_declares_fetchers_extra() -> None:
    """Régression : scrape_pass.py/enrich_pass_offers.py/scrape_scrapling.py importent
    scrapling.fetchers, qui a besoin de l'extra [fetchers] pour curl_cffi/patchright."""
    reqs = _read_requirements()
    match = re.search(r"^scrapling(\[[^\]]*\])?", reqs, re.MULTILINE)
    assert match is not None, "scrapling absent de requirements.txt"
    extras = match.group(1) or ""
    assert "fetchers" in extras, (
        f"scrapling est déclaré sans l'extra [fetchers] ({match.group(0)!r}) — "
        "scrapling.fetchers.Fetcher (utilisé par scrape_pass.py etc.) ne sera pas "
        "installable sur une machine neuve."
    )


# Correspondance nom-du-module-importé -> nom-du-paquet-PyPI, pour les imports qui
# diffèrent du nom pip (les cas les plus fréquents de "requirements.txt incomplet").
IMPORT_TO_PACKAGE = {
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "yaml": "pyyaml",
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "pypdf": "pypdf",
    "pytest": "pytest",
}


def test_known_third_party_imports_are_declared() -> None:
    reqs_lower = _read_requirements().lower()
    for module_name, package_name in IMPORT_TO_PACKAGE.items():
        assert package_name.lower() in reqs_lower, (
            f"'{module_name}' est importé dans le code mais '{package_name}' n'apparaît "
            "pas dans requirements.txt"
        )
