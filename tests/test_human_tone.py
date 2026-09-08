"""Tests unitaires pour la checklist de ton humain (N1, scripts/check_human_tone.py)."""
from typing import Any, Dict

from check_human_tone import check_text, extract_texts_from_lettre_vars, render_report


def test_check_text_clean_passes() -> None:
    result = check_text("Votre offre de Data Scientist a retenu mon attention et correspond à mon parcours.")
    assert result["ok"] is True
    assert result["chars_interdits"] == []
    assert result["formules_creuses"] == []


def test_check_text_detects_em_dash() -> None:
    result = check_text("Votre offre — particulièrement intéressante — a retenu mon attention.")
    assert result["ok"] is False
    assert "—" in result["chars_interdits"]


def test_check_text_detects_ampersand() -> None:
    result = check_text("Compétences en Data & IA.")
    assert result["ok"] is False
    assert "&" in result["chars_interdits"]


def test_check_text_detects_cliche_phrase() -> None:
    result = check_text("Je suis convaincu que mon profil correspond parfaitement à vos attentes.")
    assert result["ok"] is False
    assert len(result["formules_creuses"]) >= 1


def test_extract_texts_from_lettre_vars_flattens_all_shapes() -> None:
    data: Dict[str, Any] = {
        "objet": "Candidature au poste de Data Scientist",
        "paragraphes": [
            "Premier paragraphe.",
            {"texte": "Deuxième paragraphe.", "points": ["Point A", "Point B"]},
            ["Puce C", "Puce D"],
        ],
    }
    texts = extract_texts_from_lettre_vars(data)
    assert "Premier paragraphe." in texts
    assert "Deuxième paragraphe." in texts
    assert "Point A" in texts and "Point B" in texts
    assert "Puce C" in texts and "Puce D" in texts
    assert "Candidature au poste de Data Scientist" in texts


def test_render_report_ok() -> None:
    assert "✅" in render_report("test", {"ok": True, "chars_interdits": [], "formules_creuses": []})


def test_render_report_warns() -> None:
    txt = render_report("test", {"ok": False, "chars_interdits": ["—"], "formules_creuses": []})
    assert "⚠️" in txt
    assert "tiret cadratin" in txt
