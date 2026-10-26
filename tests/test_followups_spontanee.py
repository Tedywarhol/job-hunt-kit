"""Relances des candidatures spontanées IA : séquence J+7 / J+14, modèles, absence de synchro Notion.

Aucun appel réel à Gmail ni à Notion : find_reply, create_draft et le profil sont mockés. Personnes fictives.
"""
from datetime import date, timedelta
from typing import Any, Dict
import unittest.mock as mock

from check_human_tone import check_politesse, check_text
from followups_spontanee import TEMPLATES, build, date_en_francais, nom_affiche
from run_followups import SEQUENCE_SPONTANEE, next_step, process_entry, sync_notion

PERSONAL = {"nom": "Jean Dupont", "email": "jean.dupont@test.example"}


def _entry(etape: str = "J+0", jours_ecoules: int = 0, **overrides: Any) -> Dict[str, Any]:
    envoi = (date.today() - timedelta(days=jours_ecoules)).isoformat()
    entry: Dict[str, Any] = {
        "email": "jeanne.martin@acme-aero.example", "entreprise": "Acme Aero", "poste": "alternance en IA",
        "etape": etape, "date_j0": envoi, "date_creation_brouillon": envoi, "prenom": "Jeanne",
        "objet": "Alternance en IA : un cas d'usage pour votre équipe", "type": "spontanee",
        "sequence": list(SEQUENCE_SPONTANEE), "sans_notion": True, "relances": [],
    }
    entry.update(overrides)
    return entry


def _traiter(entry: Dict[str, Any], apply_changes: bool = True) -> Dict[str, str]:
    return process_entry(entry, service=mock.MagicMock(), token=None, db_id=None, apply_changes=apply_changes)


def test_sequence_spontanee_espace_les_relances_de_sept_jours() -> None:
    assert next_step("J+0", SEQUENCE_SPONTANEE) == "J+7"
    assert next_step("J+7", SEQUENCE_SPONTANEE) == "J+14"
    assert next_step("J+14", SEQUENCE_SPONTANEE) is None


def test_date_en_francais() -> None:
    assert date_en_francais("2026-10-01") == "1er octobre"
    assert date_en_francais("2026-10-05") == "5 octobre"
    assert date_en_francais("2026-12-31") == "31 décembre"


def test_le_corps_est_typographie_mais_l_objet_reste_celui_du_fil() -> None:
    relance = build("J+7", _entry(), "Jean Dupont")
    assert "bref\xa0?" in relance["corps"] and "\n\nBien cordialement," in relance["corps"]
    assert relance["objet"] == "Re: Alternance en IA : un cas d'usage pour votre équipe"


def test_modeles_polis_sans_tiret_cadratin_ni_placeholder() -> None:
    for etape in TEMPLATES:
        corps = build(etape, _entry(), "Jean Dupont")["corps"]
        assert check_politesse(corps) == [], f"{etape} : politesse manquante"
        assert check_text(corps)["ok"], f"{etape} : {check_text(corps)}"
        assert "—" not in corps and "&" not in corps and "{" not in corps
        assert corps.startswith("Bonjour Jeanne,") and corps.rstrip().endswith("Jean Dupont")


def test_la_premiere_relance_cite_la_date_du_premier_message() -> None:
    entry = _entry(date_j0="2026-10-05")
    assert "mon message du 5 octobre" in build("J+7", entry, "Jean Dupont")["corps"]


def test_l_objet_reprend_celui_du_premier_mail() -> None:
    assert build("J+7", _entry(), "Jean Dupont")["objet"] == "Re: Alternance en IA : un cas d'usage pour votre équipe"
    assert build("J+7", _entry(objet=""), "Jean Dupont")["objet"] == "Re: Alternance en IA"


def test_sans_prenom_la_salutation_reste_correcte() -> None:
    assert build("J+7", _entry(prenom=""), "Jean Dupont")["corps"].startswith("Bonjour,")


@mock.patch("run_followups.find_reply", return_value=None)
def test_pas_de_relance_avant_sept_jours(_: mock.MagicMock) -> None:
    entry = _entry(jours_ecoules=3)  # le moteur des offres relancerait déjà à J+3
    result = _traiter(entry)
    assert result["action"] == "aucune" and "échéance J+7 dans 4 j" in result["detail"]
    assert entry["etape"] == "J+0"


@mock.patch("run_followups.load_personal", return_value=PERSONAL)
@mock.patch("run_followups.create_draft", return_value={"id": "brouillon-1"})
@mock.patch("run_followups.find_reply", return_value=None)
def test_relance_a_sept_jours_avec_le_modele_spontane(_: mock.MagicMock, creer: mock.MagicMock, __: mock.MagicMock) -> None:
    entry = _entry(jours_ecoules=7)
    assert _traiter(entry)["action"] == "brouillon J+7 créé"
    objet, corps = creer.call_args.args[2], creer.call_args.args[3]
    assert objet.startswith("Re: Alternance en IA") and "candidature au poste" not in corps
    assert entry["etape"] == "J+7"


@mock.patch("run_followups.load_personal", return_value=PERSONAL)
@mock.patch("run_followups.create_draft", return_value={"id": "brouillon-2"})
@mock.patch("run_followups.find_reply", return_value=None)
def test_deuxieme_relance_a_quatorze_jours_puis_cloture(_: mock.MagicMock, __: mock.MagicMock, ___: mock.MagicMock) -> None:
    entry = _entry(etape="J+7", jours_ecoules=13)
    assert "échéance J+14 dans 1 j" in _traiter(entry)["detail"]
    entry = _entry(etape="J+7", jours_ecoules=14)
    assert _traiter(entry)["action"] == "brouillon J+14 créé"
    assert _traiter(entry)["action"] == "clôturée"
    assert entry["etape"] == "Terminé"


@mock.patch("run_followups.create_draft")
@mock.patch("run_followups.find_reply", return_value="fil-1")
def test_une_reponse_arrete_la_sequence_spontanee(_: mock.MagicMock, creer: mock.MagicMock) -> None:
    entry = _entry(jours_ecoules=20)
    assert _traiter(entry)["action"] == "réponse détectée"
    creer.assert_not_called()


@mock.patch("run_followups.notion_page_id")
def test_une_entree_spontanee_ne_touche_pas_notion(page: mock.MagicMock) -> None:
    sync_notion("jeton", "base", _entry(), "J+7", None, None)
    page.assert_not_called()
    sync_notion("jeton", "base", _entry(sans_notion=False), "J+7", None, None)
    page.assert_called_once()


def test_nom_affiche_met_le_nom_de_famille_en_casse_normale() -> None:
    assert nom_affiche("Jean DUPONT") == "Jean Dupont"
    assert nom_affiche("Anne DUPONT-MARTIN") == "Anne Dupont-Martin"
    assert nom_affiche("Jean Dupont") == "Jean Dupont"
    assert nom_affiche("Marie J. LEROY") == "Marie J. Leroy"


def test_la_relance_est_signee_avec_le_nom_d_affichage() -> None:
    corps = build("J+7", _entry(), "Jean DUPONT")["corps"]
    assert corps.rstrip().endswith("Jean Dupont") and "DUPONT" not in corps
