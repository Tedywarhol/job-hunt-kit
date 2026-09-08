"""Tests unitaires pour la couche Notion (scripts/push_notion.py).

Zone identifiée à 0% de couverture dans l'audit du 2026-09-07 (M5.2) — c'est la
source de vérité du statut des candidatures (dashboard, moteur de relances,
check_consistency), elle doit être fiable. Aucun appel réseau réel ici :
push_notion.api est mocké.
"""
from typing import Any, Dict, List
import unittest.mock as mock

import pytest

from push_notion import (
    database_id_from_url,
    existing_links,
    fetch_all_pages,
    find_page_by_entreprise_poste,
    find_similar_existing,
    norm_key,
)


def test_database_id_from_url_formats_uuid() -> None:
    url = "https://app.notion.com/p/3b437a76d2a7451694a03c28680b630b"
    db_id = database_id_from_url(url)
    assert db_id == "3b437a76-d2a7-4516-94a0-3c28680b630b"


def test_database_id_from_url_rejects_template_placeholder() -> None:
    """Régression 2026-09-08 : le placeholder de config/notion.template.json
    ("https://www.notion.so/<votre-base>", Notion pas encore configuré) produisait
    silencieusement un ID corrompu au lieu d'une erreur claire."""
    with pytest.raises(SystemExit, match="init.py"):
        database_id_from_url("https://www.notion.so/<votre-base>")


def _page(lien: str = "") -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    if lien:
        props["Lien offre"] = {"url": lien}
    return {"properties": props}


@mock.patch("push_notion.api")
def test_fetch_all_pages_follows_pagination(mock_api: mock.MagicMock) -> None:
    mock_api.side_effect = [
        {"results": [_page("https://a"), _page("https://b")], "has_more": True, "next_cursor": "cur1"},
        {"results": [_page("https://c")], "has_more": False},
    ]
    pages = fetch_all_pages("token", "db-id")
    assert len(pages) == 3
    assert mock_api.call_count == 2
    # Le 2e appel doit transmettre le curseur reçu du 1er.
    second_call_body = mock_api.call_args_list[1].args[3]
    assert second_call_body["start_cursor"] == "cur1"


@mock.patch("push_notion.api")
def test_existing_links_extracts_urls(mock_api: mock.MagicMock) -> None:
    mock_api.return_value = {"results": [_page("https://a"), _page(""), _page("https://b")], "has_more": False}
    links = existing_links("token", "db-id")
    assert links == {"https://a", "https://b"}


@mock.patch("push_notion.api")
def test_find_page_by_entreprise_poste_unique_match(mock_api: mock.MagicMock) -> None:
    mock_api.return_value = {"results": [{"id": "page-123"}]}
    pid = find_page_by_entreprise_poste("token", "db-id", "Acme", "Data Scientist")
    assert pid == "page-123"


@mock.patch("push_notion.api")
def test_find_page_by_entreprise_poste_no_match_returns_none(mock_api: mock.MagicMock) -> None:
    mock_api.return_value = {"results": []}
    assert find_page_by_entreprise_poste("token", "db-id", "Acme", "Data Scientist") is None


@mock.patch("push_notion.api")
def test_find_page_by_entreprise_poste_ambiguous_match_returns_none(mock_api: mock.MagicMock) -> None:
    """Plusieurs résultats -> on ne devine pas, on ne renvoie rien (mieux vaut ne pas
    synchroniser que d'écrire sur la mauvaise offre)."""
    mock_api.return_value = {"results": [{"id": "page-1"}, {"id": "page-2"}]}
    assert find_page_by_entreprise_poste("token", "db-id", "Acme", "Data Scientist") is None


def test_norm_key_strips_accents_and_case() -> None:
    assert norm_key("Ministère des Armées") == norm_key("ministere DES armees")


def _page_with(entreprise: str, poste: str) -> Dict[str, Any]:
    return {"properties": {
        "Entreprise": {"type": "title", "title": [{"plain_text": entreprise}]},
        "Poste": {"type": "rich_text", "rich_text": [{"plain_text": poste}]},
    }}


def test_find_similar_existing_detects_near_duplicate() -> None:
    """Cas réel rencontré le 2026-09-07 (Doctolib) : même offre, republiée avec une
    référence en plus dans le titre."""
    pages = [_page_with("Doctolib", "AI Data Engineer / DataOps (Réf: 7832337003)")]
    result = find_similar_existing(pages, "Doctolib", "AI Data Engineer / DataOps")
    assert result is not None
    _, ratio = result
    assert ratio >= 0.7


def test_find_similar_existing_ignores_unrelated_offers() -> None:
    pages = [_page_with("Acme", "Comptable Général")]
    assert find_similar_existing(pages, "Doctolib", "AI Data Engineer") is None


def test_find_similar_existing_requires_matching_entreprise() -> None:
    """Même intitulé de poste, entreprise différente -> pas un doublon."""
    pages = [_page_with("Axa", "Data Scientist")]
    assert find_similar_existing(pages, "Doctolib", "Data Scientist") is None


def test_find_similar_existing_does_not_confuse_different_roles_same_company() -> None:
    """Deux offres bien distinctes chez la même entreprise ne doivent pas être confondues
    (vérifié à la main : Data Scientist vs Data Engineer ~0.59 de similarité de poste,
    sous le seuil par défaut de 0.7 — cf. commentaire de find_similar_existing)."""
    pages = [_page_with("Doctolib", "Data Scientist")]
    assert find_similar_existing(pages, "Doctolib", "Data Engineer") is None


def test_find_similar_existing_respects_custom_thresholds() -> None:
    pages = [_page_with("Acme", "Data Scientist")]
    assert find_similar_existing(pages, "Acme", "Data Scientist Senior", poste_threshold=0.99) is None
    assert find_similar_existing(pages, "Acme", "Data Scientist Senior", poste_threshold=0.5) is not None
