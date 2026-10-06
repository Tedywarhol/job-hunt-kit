"""Données du tableau de bord de l'interface graphique : échéances, statuts, réseau, dossiers."""
from datetime import date
import json
import os

import pytest

import ui_data

AUJOURDHUI = date(2026, 10, 6)


def entry(etape: str, j0: str, **extra):
    return {"entreprise": "Acme Aero", "poste": "Data analyst", "etape": etape, "date_j0": j0, **extra}


def test_followups_lists_due_late_and_soon_but_not_far_or_closed():
    entries = [
        entry("J+0", "2026-10-03"),                       # J+3 : échéance le 06/10, aujourd'hui
        entry("J+3", "2026-09-20"),                       # J+5 : échéance le 25/09, 11 jours de retard
        entry("J+0", "2026-10-05"),                       # J+3 : échéance le 08/10, dans 2 jours
        entry("J+0", "2026-10-06"),                       # J+3 : échéance le 09/10, dans 3 jours (limite)
        entry("J+0", "2026-10-07"),                       # J+3 : échéance le 10/10, hors horizon
        entry("Réponse reçue", "2026-09-01"),             # séquence close
        entry("J+10", "2026-09-01"),                      # plus d'étape suivante
        {"entreprise": "Sans date", "etape": "J+0"},      # entrée incomplète
    ]
    result = ui_data.followups(entries, AUJOURDHUI)
    assert [(r["etape_suivante"], r["jours"]) for r in result] == [("J+5", -11), ("J+3", 0), ("J+3", 2), ("J+3", 3)]
    assert result[0]["echeance"] == "2026-09-25"


def test_followups_falls_back_to_draft_creation_date():
    anchor = {"entreprise": "Acme Aero", "poste": "Data", "etape": "J+0", "date_creation_brouillon": "2026-10-03"}
    assert ui_data.followups([anchor], AUJOURDHUI)[0]["jours"] == 0


def test_statuts_locaux_groups_free_text_notes():
    entries = [
        {"statut": "Brouillon créé"}, {"statut": "Envoyé"},
        {"statut": "Réponse reçue (refus, audit mail du 2026-09-15)"}, {"statut": "Réponse reçue"},
        {"statut": "Entretien équipe passé le 2026-09-29"}, {},
    ]
    assert ui_data.statuts_locaux(entries) == {"Brouillon créé": 1, "Envoyé": 1, "Réponse reçue": 2, "Suivi libre": 2}


def test_network_summary_counts_levels_and_lists_opportunities():
    network = {"genere_le": "2026-10-06", "entreprises": [{}, {}], "contacts": [
        {"nom": "Laura Blanc", "email": "laura@exemplia.fr", "entreprise": "Exemplia", "niveau": "Opportunité", "priorite": "1"},
        {"nom": "", "email": "paul@conseil-exemple.com", "entreprise": "Conseil", "niveau": "Refus", "priorite": "4"},
    ]}
    summary = ui_data.network_summary(network, {"refus": {"a": [], "b": []}})
    assert summary["niveaux_calcules"] is True
    assert summary["par_niveau"]["Opportunité"] == 1 and summary["par_niveau"]["Refus"] == 1
    assert summary["opportunites"] == [{"nom": "Laura Blanc", "entreprise": "Exemplia"}]
    assert (summary["contacts"], summary["entreprises"], summary["refus"]) == (2, 2, 2)


def test_network_summary_flags_a_base_built_before_trust_levels():
    network = {"contacts": [{"email": "a@exemple.fr", "entreprise": "A"}], "entreprises": []}
    assert ui_data.network_summary(network, None)["niveaux_calcules"] is False
    assert ui_data.network_summary(None, None) is None


def test_top_offers_sorted_by_score_and_tolerant_to_missing_fields():
    offers = [{"entreprise": "B", "poste": "Data", "score": 70}, {"administration": "Ministère exemple", "titre": "IA", "score": 91}, {}]
    result = ui_data.top_offers(offers, limit=2)
    assert [o["score"] for o in result] == [91, 70]
    assert result[0]["entreprise"] == "Ministère exemple" and result[0]["poste"] == "IA"


def test_recent_dossiers_orders_by_modification_and_detects_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_data, "ROOT", str(tmp_path))
    for index, slug in enumerate(["ancien", "recent"]):
        folder = tmp_path / "outputs" / slug
        folder.mkdir(parents=True)
        os.utime(folder, (1_700_000_000 + index * 100, 1_700_000_000 + index * 100))
    (tmp_path / "outputs" / "recent" / "CV.pdf").write_bytes(b"%PDF")
    apps = [{"slug": "ancien", "entreprise": "Ancien SA"}, {"slug": "recent", "entreprise": "Récent SA", "poste": "Data"}]
    result = ui_data.recent_dossiers(apps)
    assert [d["slug"] for d in result] == ["recent", "ancien"]
    assert [d["pdf"] for d in result] == [True, False]


def test_notion_block_is_none_without_snapshot_and_plain_json_with_one():
    assert ui_data.notion_block(None) is None
    from collections import Counter
    block = ui_data.notion_block({"total": 3, "statuts": Counter({"Postulé": 2, "Refusé": 1}), "relances_en_retard": []})
    assert json.loads(json.dumps(block)) == {"total": 3, "statuts": {"Postulé": 2, "Refusé": 1}, "relances_en_retard": []}


@pytest.mark.parametrize("with_notion", [False])
def test_build_payload_is_json_serialisable_and_skips_notion_on_request(monkeypatch, tmp_path, with_notion):
    monkeypatch.setattr(ui_data, "ROOT", str(tmp_path))
    monkeypatch.setattr(ui_data, "NETWORK_PATH", str(tmp_path / "network.json"))
    monkeypatch.setattr(ui_data, "REFUS_PATH", str(tmp_path / "refus.json"))
    monkeypatch.setattr(ui_data, "load_outreach", lambda: [entry("J+0", "2026-10-03")])
    monkeypatch.setattr(ui_data.dashboard, "load_all_opportunities", lambda: [{"entreprise": "Acme", "poste": "Data", "score": 80, "age_jours": 2}])
    monkeypatch.setattr(ui_data.dashboard, "get_application_folders", lambda: [])
    monkeypatch.setattr(ui_data.dashboard, "load_notion_snapshot", lambda: pytest.fail("Notion ne doit pas être appelé"))
    payload = ui_data.build_payload(with_notion=with_notion, today=AUJOURDHUI)
    json.dumps(payload, ensure_ascii=False)
    assert payload["notion"] is None and payload["reseau"] is None
    assert payload["relances"][0]["jours"] == 0
    assert payload["dossiers"] == {"total": 0, "recents": []}


def test_demo_payload_is_fictional_complete_and_reads_nothing(monkeypatch):
    """Même forme que le vrai tableau de bord, mais sans toucher à state/, outputs/ ni Notion."""
    for name in ("load_outreach",):
        monkeypatch.setattr(ui_data, name, lambda: pytest.fail("le mode démo ne doit rien lire"))
    monkeypatch.setattr(ui_data.dashboard, "load_notion_snapshot", lambda: pytest.fail("Notion appelé"))
    demo = ui_data.demo_payload(AUJOURDHUI)
    real = {"genere_le", "relances", "statuts_locaux", "notion", "fraicheur", "offres", "dossiers", "reseau"}
    assert set(demo) == real
    assert sorted(r["jours"] for r in demo["relances"]) == [-4, 0, 2]
    assert demo["reseau"]["niveaux_calcules"] is True
    assert set(demo["reseau"]["par_niveau"]) == set(ui_data.TRUST_LEVELS.values())
    text = json.dumps(demo, ensure_ascii=False)
    assert "invalid" in text and "@" not in text  # liens d'exemple seulement, aucune adresse
