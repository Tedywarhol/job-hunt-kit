"""Tests unitaires pour la checklist de ton humain (N1, scripts/check_human_tone.py)."""
from typing import Any, Dict

from check_human_tone import check_politesse, check_text, extract_texts_from_lettre_vars, render_report


def test_check_text_signale_la_posture_repetitive() -> None:
    """Retour du 2026-10-03 : ne pas demander à chaque fois une place, puis une redirection."""
    mail = ("Si votre équipe a besoin d'un alternant, je serais heureux d'en discuter. Dans le cas contraire, "
            "je vous serais reconnaissant de m'indiquer la bonne personne.")
    result = check_text(mail)
    assert result["ok"] is False
    assert "la bonne personne" in result["postures_repetitives"]
    assert "besoin d'un alternant" in result["postures_repetitives"]
    assert "posture répétitive" in render_report("mail", result)


def test_check_text_accepte_une_presentation_sans_exigence() -> None:
    mail = ("Je ne sais pas si une place d'alternant est ouverte dans vos équipes en ce moment. Je tenais simplement "
            "à ce que vous sachiez qui je suis, au cas où une alternance se présenterait, maintenant ou plus tard.")
    assert check_text(mail)["postures_repetitives"] == []


def test_check_politesse_accepte_un_mail_complet() -> None:
    mail = (
        "Bonjour Pierre Garnier,\n\nJ'espère que vous allez bien. Je vous écris sur les conseils de Julien.\n\n"
        "Je vous remercie par avance pour le temps que vous m'accorderez.\n\nBien cordialement,\nCamille"
    )
    assert check_politesse(mail) == []


def test_check_politesse_signale_un_mail_trop_sec() -> None:
    # Le mail jugé « sans cœur » le 2026-10-03 : aucune formule d'attention, ni remerciement, ni formule de fin.
    manque = check_politesse("Bonjour,\n\nJe suis disponible mardi entre 12 h et 17 h.\n\nCamille")
    assert len(manque) == 2
    assert any("remerciement" in m for m in manque)
    assert any("formule de fin" in m for m in manque)


def test_check_politesse_reconnait_les_voeux_de_fin() -> None:
    for fin in ("Très bonne journée", "Excellente semaine", "Bonne continuation", "Bien à vous"):
        assert not any("formule de fin" in m for m in check_politesse(f"Bonjour, merci. {fin}."))


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
