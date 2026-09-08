"""Tests unitaires pour l'analyse rétroactive du taux de réponse (E4, scripts/analyze_response_rates.py)."""
from typing import Any, Dict, List

from analyze_response_rates import extract_rows, group_stats, render_group, score_bucket_stats


def _page(statut: str, ats: str = "", source: str = "", score: Any = None) -> Dict[str, Any]:
    props: Dict[str, Any] = {"Statut": {"select": {"name": statut}}}
    if ats:
        props["ATS"] = {"select": {"name": ats}}
    if source:
        props["Source"] = {"select": {"name": source}}
    if score is not None:
        props["Score"] = {"number": score}
    return {"properties": props}


def test_extract_rows_reads_properties() -> None:
    rows = extract_rows([_page("Postulé", ats="Greenhouse", source="ATS", score=85)])
    assert rows[0] == {"statut": "Postulé", "ats": "Greenhouse", "source": "ATS", "score": 85}


def test_group_stats_computes_rate_per_group() -> None:
    rows = [
        {"statut": "Postulé", "ats": "Greenhouse", "source": "x", "score": None},
        {"statut": "Entretien", "ats": "Greenhouse", "source": "x", "score": None},
        {"statut": "Refusé", "ats": "Lever", "source": "x", "score": None},
        {"statut": "À traiter", "ats": "Lever", "source": "x", "score": None},  # jamais postulé -> ignoré
    ]
    stats = group_stats(rows, "ats")
    assert stats["Greenhouse"] == {"postule": 2, "reponse": 1, "taux_pct": 50.0}
    assert stats["Lever"] == {"postule": 1, "reponse": 1, "taux_pct": 100.0}


def test_group_stats_ignores_non_postule_statuts() -> None:
    rows = [{"statut": "Écartée", "ats": "Greenhouse", "source": "x", "score": None}]
    assert group_stats(rows, "ats") == {}


def test_score_bucket_stats_buckets_correctly() -> None:
    rows = [
        {"statut": "Postulé", "ats": "", "source": "", "score": 95},
        {"statut": "Entretien", "ats": "", "source": "", "score": 92},
        {"statut": "Postulé", "ats": "", "source": "", "score": 65},
    ]
    stats = score_bucket_stats(rows)
    assert stats["90-100"]["postule"] == 2
    assert stats["90-100"]["reponse"] == 1
    assert stats["<70"]["postule"] == 1


def test_score_bucket_stats_ignores_missing_score() -> None:
    rows = [{"statut": "Postulé", "ats": "", "source": "", "score": None}]
    stats = score_bucket_stats(rows)
    assert all(c["postule"] == 0 for c in stats.values())


def test_render_group_handles_empty_stats() -> None:
    assert "pas assez de données" in render_group("Par ATS", {})
