"""Tests unitaires pour le contrôle de cohérence (scripts/check_consistency.py).

Utilise des fichiers temporaires (pas les vrais state/outreach.json ni outputs/ du
projet) et un index Notion fabriqué à la main — aucun appel réseau.
"""
import json
import os
from datetime import date, timedelta
from typing import Any, Dict

from check_consistency import (
    check_outputs_vs_notion,
    check_outreach_vs_notion,
    check_relances_dues,
    find_notion_row,
    norm_key,
)


def _index(rows: Dict[str, Any]) -> Dict[str, Any]:
    """rows : {url_ou_vide: {"statut":..., "entreprise":..., "poste":...}}"""
    by_url: Dict[str, Any] = {}
    by_key: Dict[Any, Any] = {}
    for url, row in rows.items():
        if url:
            by_url[url] = row
        key = (norm_key(row["entreprise"]), norm_key(row["poste"]))
        by_key.setdefault(key, []).append(row)
    return {"by_url": by_url, "by_key": by_key, "total": len(rows)}


def test_norm_key_strips_accents_and_case() -> None:
    assert norm_key("Ministère des Armées") == norm_key("ministere DES armees")


def test_find_notion_row_by_url() -> None:
    idx = _index({"https://a": {"statut": "Postulé", "entreprise": "Acme", "poste": "DS"}})
    row = find_notion_row(idx, "https://a", "autre chose", "autre poste")
    assert row is not None and row["statut"] == "Postulé"


def test_find_notion_row_by_key_when_unique() -> None:
    idx = _index({"": {"statut": "À traiter", "entreprise": "Acme", "poste": "Data Scientist"}})
    row = find_notion_row(idx, "", "Acme", "Data Scientist")
    assert row is not None and row["statut"] == "À traiter"


def test_find_notion_row_ambiguous_returns_none() -> None:
    by_url: Dict[str, Any] = {}
    by_key = {(norm_key("Acme"), norm_key("Data Scientist")): [
        {"statut": "Postulé", "entreprise": "Acme", "poste": "Data Scientist"},
        {"statut": "À traiter", "entreprise": "Acme", "poste": "Data Scientist"},
    ]}
    idx = {"by_url": by_url, "by_key": by_key, "total": 2}
    assert find_notion_row(idx, "", "Acme", "Data Scientist") is None


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def test_check_outreach_vs_notion_flags_missing_page(tmp_path: Any) -> None:
    outreach_path = os.path.join(str(tmp_path), "outreach.json")
    _write_json(outreach_path, [{"entreprise": "Inconnu Corp", "poste": "Data Scientist", "etape": "J+3"}])
    idx = _index({})  # base Notion vide -> aucune correspondance possible
    errors, warnings = check_outreach_vs_notion(idx, outreach_path=outreach_path)
    assert len(errors) == 1
    assert "introuvable dans Notion" in errors[0]
    assert warnings == []


def test_check_outreach_vs_notion_flags_status_divergence(tmp_path: Any) -> None:
    outreach_path = os.path.join(str(tmp_path), "outreach.json")
    _write_json(outreach_path, [{"entreprise": "Acme", "poste": "Data Scientist", "etape": "Réponse reçue"}])
    idx = _index({"": {"statut": "Postulé", "entreprise": "Acme", "poste": "Data Scientist"}})
    errors, warnings = check_outreach_vs_notion(idx, outreach_path=outreach_path)
    assert errors == []
    assert len(warnings) == 1
    assert "réponse reçue localement" in warnings[0]


def test_check_outreach_vs_notion_clean_case(tmp_path: Any) -> None:
    outreach_path = os.path.join(str(tmp_path), "outreach.json")
    _write_json(outreach_path, [{"entreprise": "Acme", "poste": "Data Scientist", "etape": "J+3"}])
    idx = _index({"": {"statut": "Postulé", "entreprise": "Acme", "poste": "Data Scientist"}})
    errors, warnings = check_outreach_vs_notion(idx, outreach_path=outreach_path)
    assert errors == [] and warnings == []


def test_check_outreach_vs_notion_no_file_returns_empty(tmp_path: Any) -> None:
    missing = os.path.join(str(tmp_path), "does-not-exist.json")
    errors, warnings = check_outreach_vs_notion(_index({}), outreach_path=missing)
    assert errors == [] and warnings == []


def test_check_relances_dues_flags_overdue(tmp_path: Any) -> None:
    outreach_path = os.path.join(str(tmp_path), "outreach.json")
    anchor = (date.today() - timedelta(days=10)).isoformat()
    _write_json(outreach_path, [
        {"entreprise": "Acme", "poste": "Data Scientist", "etape": "J+3", "date_creation_brouillon": anchor},
        {"entreprise": "Beta", "poste": "Data Analyst", "etape": "Réponse reçue", "date_creation_brouillon": anchor},
    ])
    infos = check_relances_dues(outreach_path=outreach_path)
    assert len(infos) == 1  # Beta est en séquence terminée, jamais signalée
    assert "Acme" in infos[0]
    assert "J+5" in infos[0]  # prochaine étape après J+3


def test_check_relances_dues_not_yet_due(tmp_path: Any) -> None:
    outreach_path = os.path.join(str(tmp_path), "outreach.json")
    anchor = date.today().isoformat()
    _write_json(outreach_path, [{"entreprise": "Acme", "poste": "Data Scientist", "etape": "J+0", "date_creation_brouillon": anchor}])
    assert check_relances_dues(outreach_path=outreach_path) == []


def _make_output_folder(base: str, slug: str, entreprise: str, poste: str) -> None:
    folder = os.path.join(base, slug)
    os.makedirs(folder, exist_ok=True)
    _write_json(os.path.join(folder, "lettre-vars.json"), {"entreprise": entreprise, "poste": poste})
    with open(os.path.join(folder, "CV_Test.pdf"), "wb") as f:
        f.write(b"%PDF-fake")


def test_check_outputs_vs_notion_flags_stale_a_traiter(tmp_path: Any) -> None:
    outputs_dir = str(tmp_path)
    _make_output_folder(outputs_dir, "acme-data-scientist", "Acme", "Data Scientist")
    idx = _index({"": {"statut": "À traiter", "entreprise": "Acme", "poste": "Data Scientist"}})
    warnings = check_outputs_vs_notion(idx, outputs_dir=outputs_dir)
    assert len(warnings) == 1
    assert "acme-data-scientist" in warnings[0]


def test_check_outputs_vs_notion_prefers_real_lien_over_synthetic(tmp_path: Any) -> None:
    """M6 (audit 2026-09-07) : quand lettre-vars.json trace le vrai lien de l'offre, il
    prime sur le lien synthétique https://job-hunt/<slug>."""
    outputs_dir = str(tmp_path)
    folder = os.path.join(outputs_dir, "acme-data-scientist")
    os.makedirs(folder, exist_ok=True)
    _write_json(os.path.join(folder, "lettre-vars.json"), {"entreprise": "Acme", "poste": "Peu importe", "lien": "https://vraie-offre.example/123"})
    with open(os.path.join(folder, "CV_Test.pdf"), "wb") as f:
        f.write(b"%PDF-fake")
    idx = _index({"https://vraie-offre.example/123": {"statut": "Postulé", "entreprise": "Acme", "poste": "Data Scientist"}})
    assert check_outputs_vs_notion(idx, outputs_dir=outputs_dir) == []


def test_check_outputs_vs_notion_matches_synthetic_job_hunt_link(tmp_path: Any) -> None:
    """Les pages Notion créées sans URL d'offre d'origine portent un lien synthétique
    https://job-hunt/<slug> (vérifié sur les données réelles du 2026-09-07) — plus fiable
    qu'un match texte entreprise/poste, à essayer en premier."""
    outputs_dir = str(tmp_path)
    _make_output_folder(outputs_dir, "acme-data-scientist", "Acme", "Data Scientist (texte différent de Notion)")
    idx = _index({"https://job-hunt/acme-data-scientist": {"statut": "Postulé", "entreprise": "Acme", "poste": "Tout autre libellé"}})
    assert check_outputs_vs_notion(idx, outputs_dir=outputs_dir) == []


def test_check_outputs_vs_notion_clean_when_postule(tmp_path: Any) -> None:
    outputs_dir = str(tmp_path)
    _make_output_folder(outputs_dir, "acme-data-scientist", "Acme", "Data Scientist")
    idx = _index({"": {"statut": "Postulé", "entreprise": "Acme", "poste": "Data Scientist"}})
    assert check_outputs_vs_notion(idx, outputs_dir=outputs_dir) == []


def test_check_outputs_vs_notion_skips_folders_without_pdf(tmp_path: Any) -> None:
    outputs_dir = str(tmp_path)
    folder = os.path.join(outputs_dir, "draft-only")
    os.makedirs(folder, exist_ok=True)
    _write_json(os.path.join(folder, "lettre-vars.json"), {"entreprise": "Acme", "poste": "Data Scientist"})
    assert check_outputs_vs_notion(_index({}), outputs_dir=outputs_dir) == []
