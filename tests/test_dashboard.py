"""Tests unitaires pour le module dashboard.py."""
from typing import Any, Dict, List
import unittest.mock as mock

from dashboard import (
    compute_freshness_kpis,
    get_application_folders,
    load_all_opportunities,
    load_notion_snapshot,
    render_follow_up_radar,
    render_freshness_box,
    render_notion_funnel,
    render_relances_en_retard,
    render_top_fresh_offers,
)


def test_compute_freshness_kpis() -> None:
    offers: List[Dict[str, Any]] = [
        {"age_jours": 0},
        {"age_jours": 1},
        {"age_jours": 5},
        {"age_jours": 20},
        {"age_jours": 45},
    ]
    kpis = compute_freshness_kpis(offers)
    assert kpis["today"] == 2
    assert kpis["week"] == 1
    assert kpis["month"] == 1
    assert kpis["older"] == 1


def test_render_freshness_box() -> None:
    kpis = {"today": 5, "week": 10, "month": 15, "older": 2}
    box = render_freshness_box(kpis)
    assert "Offres du jour" in box
    assert "5" in box
    assert "Cette semaine" in box
    assert "10" in box


def test_render_follow_up_radar() -> None:
    apps: List[Dict[str, Any]] = [
        {"entreprise": "Dataiku", "slug": "dataiku-engineer"},
        {"entreprise": "Doctolib", "slug": "doctolib-analyst"},
    ]
    radar = render_follow_up_radar(apps)
    assert "CANDIDATURES EN COURS" in radar
    assert "Dataiku" in radar
    assert "Doctolib" in radar


def test_render_top_fresh_offers() -> None:
    offers: List[Dict[str, Any]] = [
        {"score": 95, "date_publication": "2026-09-01", "age_jours": 0, "poste": "Lead Data Scientist", "entreprise": "Tech A", "lieu": "Paris"},
        {"score": 80, "date_publication": "2026-08-25", "age_jours": 7, "poste": "Data Engineer", "entreprise": "Tech B", "lieu": "Lyon"},
    ]
    txt = render_top_fresh_offers(offers, limit=2)
    assert "Lead Data Scientist" in txt
    assert "95/100" in txt
    assert "2026-09-01" in txt
    assert "Tech A" in txt


def test_get_application_folders() -> None:
    apps = get_application_folders()
    assert isinstance(apps, list)


def _notion_page(statut: str, entreprise: str = "", poste: str = "", etape: str = "", date_prochaine: str = "") -> Dict[str, Any]:
    props: Dict[str, Any] = {"Statut": {"select": {"name": statut}}}
    if entreprise:
        props["Entreprise"] = {"type": "title", "title": [{"plain_text": entreprise}]}
    if poste:
        props["Poste"] = {"type": "rich_text", "rich_text": [{"plain_text": poste}]}
    if etape:
        props["Étape relance"] = {"select": {"name": etape}}
    if date_prochaine:
        props["Date prochaine relance"] = {"date": {"start": date_prochaine}}
    return {"properties": props}


@mock.patch("push_notion.fetch_all_pages")
@mock.patch("push_notion.get_token")
@mock.patch("push_notion.database_id_from_url")
@mock.patch("push_notion.load_cfg")
def test_load_notion_snapshot_aggregates_statuts_and_relances(
    mock_load_cfg: mock.MagicMock, mock_db_id: mock.MagicMock,
    mock_token: mock.MagicMock, mock_fetch: mock.MagicMock,
) -> None:
    mock_load_cfg.return_value = {"database_url": "https://notion.so/fake"}
    mock_db_id.return_value = "fake-db-id"
    mock_token.return_value = "fake-token"
    mock_fetch.return_value = [
        _notion_page("Postulé", "Acme", "Data Scientist", etape="J+3", date_prochaine="2000-01-01"),  # en retard
        _notion_page("À traiter"),
        _notion_page("Réponse reçue", etape="Réponse reçue", date_prochaine="2000-01-01"),  # terminal, pas en retard
    ]
    snap = load_notion_snapshot()
    assert snap is not None
    assert snap["total"] == 3
    assert snap["statuts"]["Postulé"] == 1
    assert snap["statuts"]["À traiter"] == 1
    assert len(snap["relances_en_retard"]) == 1
    assert snap["relances_en_retard"][0]["entreprise"] == "Acme"


@mock.patch("push_notion.load_cfg")
def test_load_notion_snapshot_returns_none_when_not_configured(mock_load_cfg: mock.MagicMock) -> None:
    mock_load_cfg.side_effect = SystemExit("Notion non configuré")
    assert load_notion_snapshot() is None


def test_render_notion_funnel_without_snapshot() -> None:
    assert "non configuré" in render_notion_funnel(None)


def test_render_relances_en_retard_none_due() -> None:
    txt = render_relances_en_retard({"total": 1, "statuts": {}, "relances_en_retard": []})
    assert "Aucune relance" in txt


def test_render_relances_en_retard_lists_them() -> None:
    snap = {"relances_en_retard": [{"entreprise": "Acme", "poste": "Data Scientist", "etape": "J+3", "date_prochaine": "2000-01-01"}]}
    txt = render_relances_en_retard(snap)
    assert "Acme" in txt
    assert "run_followups.py --apply" in txt

