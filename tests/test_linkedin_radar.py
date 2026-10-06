"""Tests unitaires pour le radar LinkedIn (parsing/scoring, pas d'appel réseau/MCP ici)."""
from linkedin_radar import (
    build_offer,
    competition_bonus,
    competition_note,
    parse_competition_signal,
    parse_relative_age_days,
)


def test_parse_relative_age_days() -> None:
    assert parse_relative_age_days("Boulogne-Billancourt · il y a 1 jour · 86 candidats") == 1
    assert parse_relative_age_days("Puteaux · il y a 6 jours") == 6
    assert parse_relative_age_days("Paris · Il y a 1 semaine") == 7
    assert parse_relative_age_days("Paris · il y a 2 semaines") == 14
    assert parse_relative_age_days("Paris · il y a 3 mois") == 90
    assert parse_relative_age_days("Paris · il y a 2 heures") == 0
    assert parse_relative_age_days("aucune mention de date ici") is None


def test_parse_competition_signal_candidate_count() -> None:
    signal = parse_competition_signal("Boulogne-Billancourt, Île-de-France, France · il y a 1 jour · 86 candidats")
    assert signal == {"applicant_count": 86, "is_early_applicant": False}


def test_parse_competition_signal_clicked_apply_phrasing() -> None:
    """Formulation réelle observée sur des offres alternance/stage (distincte de « X candidats »,
    vue sur des offres promues/CDI) : celle explicitement anticipée par l'utilisateur."""
    signal = parse_competition_signal(
        "Paris, Île-de-France, France · Republication il y a 5 jours · "
        "Plus de 100 personnes ont cliqué sur Postuler"
    )
    assert signal == {"applicant_count": 100, "is_early_applicant": False}


def test_parse_competition_signal_early_applicant_badge() -> None:
    signal = parse_competition_signal("Mon Consultant Indépendant\nPromu(e)\nSoyez l'un des premiers candidats")
    assert signal["is_early_applicant"] is True
    assert signal["applicant_count"] is None


def test_parse_competition_signal_absent() -> None:
    signal = parse_competition_signal("Aucune information de candidature sur cette page")
    assert signal == {"applicant_count": None, "is_early_applicant": False}


def test_competition_bonus_favors_low_competition() -> None:
    assert competition_bonus(None, True) == 15  # badge prioritaire sur le compte
    assert competition_bonus(5, False) == 12
    assert competition_bonus(20, False) == 6
    assert competition_bonus(50, False) == 0
    assert competition_bonus(86, False) == -10
    assert competition_bonus(None, False) == 0


def test_competition_note_text() -> None:
    assert competition_note(None, True) == "l'un des premiers candidats"
    assert competition_note(86, False) == "86 candidat(s)"
    assert competition_note(None, False) == "candidatures inconnues"


def test_build_offer_filters_out_of_scope_titles() -> None:
    assert build_offer("123", "Office Manager", "ACME", "Paris, France", "il y a 1 jour") is None


def test_build_offer_valid_alternance() -> None:
    detail_text = "Boulogne-Billancourt, Île-de-France, France · il y a 1 jour · 8 candidats"
    offer = build_offer("4465736200", "Ingénieur IA - Alternance (H/F)", "ALTEN", "Boulogne-Billancourt, Île-de-France", detail_text)
    assert offer is not None
    assert offer["entreprise"] == "ALTEN"
    assert offer["type"] == "alternance"
    assert offer["statut"] == "À traiter"
    assert offer["source"] == "LinkedIn"
    assert offer["lien"] == "https://www.linkedin.com/jobs/view/4465736200/"
    assert offer["age_jours"] == 1
    assert "8 candidat(s)" in offer["notes_matching"]
    # recency (base 80 + bonus jour<=1 -> +15 -> 95) + compétition (8 candidats -> +12) -> plafond 98
    assert offer["score"] == 98


def test_build_offer_early_applicant_badge_boosts_score() -> None:
    detail_text = "Ville de Paris, Île-de-France · il y a 3 jours · Soyez l'un des premiers candidats"
    offer = build_offer("999", "Alternance Data Analyst", "Thermosphr", "Paris, Île-de-France", detail_text)
    assert offer is not None
    assert "l'un des premiers candidats" in offer["notes_matching"]


def test_build_offer_defaults_age_to_zero_when_unknown() -> None:
    offer = build_offer("1", "Stage Data Scientist", "Dataiku", "Paris, France", "aucune date visible")
    assert offer is not None
    assert offer["age_jours"] == 0
