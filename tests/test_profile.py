"""Tests unitaires pour le module profile.py."""
import datetime
from typing import Any, Dict

import pytest

from profile import (
    date_lettre_aujourdhui,
    doc_base_names,
    load_cv_data,
    load_personal,
    mois_francais,
    ville_from_localisation,
)


def test_doc_base_names(dummy_personal: Dict[str, Any]) -> None:
    cv_base, lettre_base = doc_base_names(dummy_personal)
    assert cv_base == "CV_Jean_DUPONT"
    assert lettre_base == "Lettre_Jean_DUPONT"


def test_doc_base_names_special_chars() -> None:
    p = {"nom": "Éléonore-Marie D'ALEXANDRE"}
    cv_base, lettre_base = doc_base_names(p)
    assert cv_base == "CV_Éléonore-Marie_D'ALEXANDRE"
    assert lettre_base == "Lettre_Éléonore-Marie_D'ALEXANDRE"


def test_ville_from_localisation(dummy_personal: Dict[str, Any]) -> None:
    assert ville_from_localisation(dummy_personal) == "Lyon"
    assert ville_from_localisation({"localisation": "Paris (75), France"}) == "Paris"
    assert ville_from_localisation({"localisation": "Toulouse, France"}) == "Toulouse"
    assert ville_from_localisation({"localisation": ""}) == "Paris"


def test_mois_francais() -> None:
    assert mois_francais(1) == "janvier"
    assert mois_francais(7) == "juillet"
    assert mois_francais(12) == "décembre"


def test_date_lettre_aujourdhui() -> None:
    date_str = date_lettre_aujourdhui()
    today = datetime.date.today()
    assert str(today.day) in date_str
    assert str(today.year) in date_str
    assert mois_francais(today.month) in date_str


def test_load_personal_fallback() -> None:
    p = load_personal()
    assert isinstance(p, dict)
    assert "nom" in p
    assert "email" in p


def test_load_cv_data_missing_file_gives_clear_error() -> None:
    """Régression 2026-09-08 : un cv-data.json manquant (machine fraîche, init.py pas
    encore lancé) levait un traceback FileNotFoundError brut plutôt qu'un message clair."""
    with pytest.raises(SystemExit, match="init.py"):
        load_cv_data("does-not-exist/cv-data.json")
