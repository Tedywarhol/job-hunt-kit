"""Tests unitaires pour la vérification de couverture ATS (N2, scripts/check_ats_coverage.py)."""
import json
import os
from typing import Any, Dict

from check_ats_coverage import check_slug, compute_coverage, render_report

HTML_SAMPLE = """
<html><body>
<p class="profile-text">Data Scientist passionné par le Machine Learning et Python.</p>
<div class="ats-hidden-layer">ATS: Python, SQL, Power BI, GCP, Airflow</div>
</body></html>
"""


def test_compute_coverage_distinguishes_visible_from_hidden() -> None:
    keywords = ["Python", "Machine Learning", "SQL", "GCP"]
    result = compute_coverage(HTML_SAMPLE, keywords)
    assert result["total"] == 4
    # Python et Machine Learning sont dans le texte visible.
    assert result["visible_count"] == 2
    assert "SQL" in result["visible_missing"]
    assert "GCP" in result["visible_missing"]
    # SQL et GCP sont quand même couverts via la couche cachée -> coverage totale = 100%.
    assert result["full_count"] == 4
    assert result["missing_entirely"] == []


def test_compute_coverage_flags_keyword_missing_entirely() -> None:
    result = compute_coverage(HTML_SAMPLE, ["Python", "Kubernetes"])
    assert "Kubernetes" in result["missing_entirely"]
    assert "Kubernetes" in result["visible_missing"]


def test_compute_coverage_no_keywords_is_100pct() -> None:
    result = compute_coverage(HTML_SAMPLE, [])
    assert result["visible_pct"] == 100.0
    assert result["full_pct"] == 100.0


def test_render_report_warns_below_seuil() -> None:
    result = {
        "slug": "acme-data-scientist", "total": 4, "visible_count": 1, "visible_pct": 25.0,
        "full_count": 4, "full_pct": 100.0, "visible_missing": ["SQL", "GCP", "Power BI"], "missing_entirely": [],
    }
    txt = render_report(result)
    assert "⚠️" in txt
    assert "SQL" in txt


def test_render_report_ok_above_seuil() -> None:
    result = {
        "slug": "acme-data-scientist", "total": 4, "visible_count": 3, "visible_pct": 75.0,
        "full_count": 4, "full_pct": 100.0, "visible_missing": ["GCP"], "missing_entirely": [],
    }
    assert "✅" in render_report(result)


def _make_slug_folder(base: str, slug: str, keywords: Any, html: str = HTML_SAMPLE) -> str:
    folder = os.path.join(base, slug)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "cv-vars.json"), "w", encoding="utf-8") as f:
        json.dump({"mots_cles_ats": keywords}, f)
    with open(os.path.join(folder, "CV_Test.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return folder


def test_check_slug_reads_real_files(tmp_path: Any) -> None:
    base = str(tmp_path)
    _make_slug_folder(base, "acme-data-scientist", ["Python", "SQL"])
    result = check_slug("acme-data-scientist", outputs_dir=base)
    assert result is not None
    assert result["slug"] == "acme-data-scientist"
    assert result["total"] == 2


def test_check_slug_returns_none_without_keywords(tmp_path: Any) -> None:
    base = str(tmp_path)
    _make_slug_folder(base, "acme-data-scientist", [])
    assert check_slug("acme-data-scientist", outputs_dir=base) is None


def test_check_slug_returns_none_when_missing(tmp_path: Any) -> None:
    assert check_slug("does-not-exist", outputs_dir=str(tmp_path)) is None
