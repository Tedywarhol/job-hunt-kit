"""Tests des dossiers CV et lettre des spontanées (scripts/prospection_dossier.py). Aucun PDF n'est produit ici."""
import json
from typing import Any, Dict

import pytest

import prospection_dossier as pd
from check_human_tone import check_text
from prospection_dossier import composer_cv_vars, composer_lettre_vars, ecrire_dossier

FICHE: Dict[str, Any] = {
    "nom": "Acme Aero", "equipe": "construit", "service": "Direction Data",
    "accroche": "Vos publications sur les agents IA décrivent le terrain où je veux travailler.",
    "cas_usage": "Je pense à un assistant qui retrouve une règle dans vos documents, en citant sa source.",
}
METIER: Dict[str, Any] = {**FICHE, "equipe": "metier",
                          "accroche": "Votre pôle pilote des projets data côté métier, et c'est ce travail qui m'intéresse.",
                          "cas_usage": "Je peux aider à cadrer les besoins et à accompagner l'adoption des outils."}


def test_le_cv_metier_part_du_business_analyst_et_des_projets_d_analyse() -> None:
    construit, metier = composer_cv_vars(FICHE), composer_cv_vars(METIER)
    assert construit["projets_selection"] != metier["projets_selection"]
    assert "HR Analytics : Modélisation prédictive du turnover" in metier["projets_selection"]
    assert "Business Analyst" in metier["accroche"] and "Business Analyst" not in construit["accroche"]
    assert "Workflow n8n : Automatisation Mails & CRM IA" in construit["projets_selection"]


def test_le_cv_cite_l_entreprise_dans_les_mots_cles_et_garde_trois_projets() -> None:
    for fiche in (FICHE, METIER):
        cv = composer_cv_vars(fiche)
        assert cv["mots_cles_ats"][0] == "Acme Aero" and len(cv["projets_selection"]) == 3


def test_le_titre_du_cv_ne_reprend_pas_le_pari_d_une_proposition() -> None:
    for fiche in (FICHE, METIER):
        assert "assistants" not in composer_cv_vars(fiche)["titre"].lower()


def test_la_lettre_garde_le_squelette_et_les_deux_passages_propres() -> None:
    lettre = composer_lettre_vars(FICHE, "14 octobre 2026", "Paris (75)")
    paragraphes = lettre["paragraphes"]
    assert len(paragraphes) == 4
    assert paragraphes[0] == FICHE["accroche"] and paragraphes[2].startswith(FICHE["cas_usage"])
    assert "Copilot Studio" in paragraphes[2] and "dès maintenant" in paragraphes[3]
    assert lettre["destinataire"] == "Madame, Monsieur de Direction Data" and lettre["type"] == "alternance"


def test_la_lettre_metier_s_appuie_sur_le_stage_canal_plus() -> None:
    profil = composer_lettre_vars(METIER, "14 octobre 2026", "Paris (75)")["paragraphes"][1]
    assert "CANAL+" in profil and "Power BI" in profil
    assert "CANAL+" not in composer_lettre_vars(FICHE, "14 octobre 2026", "Paris (75)")["paragraphes"][1]


def test_sans_service_le_destinataire_reste_neutre() -> None:
    lettre = composer_lettre_vars({**FICHE, "service": ""}, "14 octobre 2026", "Paris (75)")
    assert lettre["destinataire"] == "Madame, Monsieur"


@pytest.mark.parametrize("fiche", [FICHE, METIER])
def test_la_lettre_composee_passe_le_controle_de_ton(fiche: Dict[str, Any]) -> None:
    texte = "\n".join(composer_lettre_vars(fiche, "14 octobre 2026", "Paris (75)")["paragraphes"])
    assert check_text(texte)["ok"] and "—" not in texte and "&" not in texte


def test_sans_equipe_la_variante_construit_s_applique() -> None:
    sans = {k: v for k, v in FICHE.items() if k != "equipe"}
    assert composer_cv_vars(sans) == composer_cv_vars(FICHE)


@pytest.mark.parametrize("manquant", ["nom", "accroche", "cas_usage"])
def test_une_fiche_incomplete_est_refusee(manquant: str, tmp_path: Any) -> None:
    with pytest.raises(ValueError, match=manquant):
        ecrire_dossier({**FICHE, manquant: " "}, str(tmp_path))


def test_un_type_d_equipe_inconnu_est_refuse(tmp_path: Any) -> None:
    with pytest.raises(ValueError, match="équipe"):
        ecrire_dossier({**FICHE, "equipe": "commerciale"}, str(tmp_path))


def test_les_deux_fichiers_de_variables_sont_ecrits(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pd, "load_personal", lambda: {"localisation": "Lyon (69), France"})
    cle = ecrire_dossier(FICHE, str(tmp_path))
    dossier = tmp_path / "outputs" / cle
    assert cle == "acme-aero"
    assert json.loads((dossier / "cv-vars.json").read_text(encoding="utf-8"))["mots_cles_ats"][0] == "Acme Aero"
    assert json.loads((dossier / "lettre-vars.json").read_text(encoding="utf-8"))["ville_candidat"] == "Lyon (69)"


def test_les_textes_recoivent_la_typographie_mais_pas_les_noms_de_projets(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pd, "load_personal", lambda: {"localisation": "Lyon (69), France"})
    cle = ecrire_dossier({**FICHE, "objet": "Candidature : l'IA"}, str(tmp_path))
    dossier = tmp_path / "outputs" / cle
    lettre = json.loads((dossier / "lettre-vars.json").read_text(encoding="utf-8"))
    cv = json.loads((dossier / "cv-vars.json").read_text(encoding="utf-8"))
    assert lettre["objet"] == "Candidature\xa0: l’IA"
    assert "\xa0:" in cv["titre"]
    assert cv["projets_selection"] == composer_cv_vars(FICHE)["projets_selection"]
