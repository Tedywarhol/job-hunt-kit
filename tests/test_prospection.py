"""Tests de l'état des candidatures spontanées IA (scripts/prospection.py).

Entreprises, domaines et personnes fictifs uniquement : le dépôt est public. Aucun accès réseau.
"""
from typing import Any, Dict, List

import pytest

from prospection import (
    ajouter_entreprise,
    ajouter_personne,
    charger,
    lignes_etat,
    lignes_plan,
    marquer_envoye,
    marquer_rebond,
    marquer_reponse,
    proposer_adresse,
    sauver,
    signature_mail,
    slug,
)

SURE = {"entreprise": "Acme Aero", "domaine": "acme-aero.example", "format": "prenom.nom", "confiance": "sûre"}
PROBABLE = {"entreprise": "Bleu Rail", "domaine": "bleu-rail.example", "format": "p.nom", "confiance": "probable"}
CONNUES: List[Dict[str, str]] = [SURE, PROBABLE]
REFUS = {"ancien@vert-mer.example": [{"date": "2026-10-01", "source": "gmail", "extrait": "pas de poste"}]}


def _etat() -> Dict[str, Any]:
    return {"entreprises": {}}


def _avec(domaine: str, nom: str = "Acme Aero") -> Dict[str, Any]:
    state = _etat()
    ajouter_entreprise(state, nom, "Lyon", "ia", domaine)
    return state


def test_slug_sans_accent_ni_ponctuation() -> None:
    assert slug("Société Générale & Co") == "societe-generale-co"


@pytest.mark.parametrize("ville,secteur", [("Atlantide", "ia"), ("Lyon", "agricole")])
def test_refuse_une_ville_ou_un_secteur_inconnu(ville: str, secteur: str) -> None:
    with pytest.raises(ValueError):
        ajouter_entreprise(_etat(), "X", ville, secteur, "x.example")


def test_refuse_un_doublon_et_nettoie_le_domaine() -> None:
    state = _etat()
    entreprise = ajouter_entreprise(state, "Acme Aero", "Lyon", "ia", " WWW.Acme-Aero.example ")
    assert entreprise["domaine"] == "acme-aero.example"
    with pytest.raises(ValueError):
        ajouter_entreprise(state, "Acme  Aero", "Nantes", "ia", "autre.example")


def test_adresse_sure_quand_le_format_est_etabli() -> None:
    assert proposer_adresse("acme-aero.example", "Jeanne", "Martin", CONNUES) == ("jeanne.martin@acme-aero.example", "sûre")


def test_adresse_devinee_quand_le_format_est_seulement_probable() -> None:
    assert proposer_adresse("bleu-rail.example", "Jeanne", "Martin", CONNUES) == ("j.martin@bleu-rail.example", "devinée")


def test_adresse_devinee_prenom_nom_pour_un_domaine_inconnu() -> None:
    assert proposer_adresse("inconnue.example", "Hélène", "D'Arc", CONNUES) == ("helene.darc@inconnue.example", "devinée")


@pytest.mark.parametrize("prenom,nom", [("Karim", "El Amrani"), ("Julie", "Martin-Durand"), ("Anne", "D'Arc"), ("Anne Sophie", "Roy")])
def test_un_nom_compose_reste_devine_meme_sur_un_format_sur(prenom: str, nom: str) -> None:
    adresse, confiance = proposer_adresse("acme-aero.example", prenom, nom, CONNUES)
    assert adresse and confiance == "devinée"


def test_un_nom_incertain_garde_l_adresse_devinee_sur_un_format_sur() -> None:
    state = _avec("acme-aero.example")
    sure = ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "manager", "x", "l1", {}, CONNUES)
    incertaine = ajouter_personne(state, "acme-aero", "Paul", "Durand", "directeur", "x", "l2", {}, CONNUES, incertain=True)
    assert sure["confiance"] == "sûre" and incertaine["confiance"] == "devinée"


def test_pas_d_adresse_sans_domaine() -> None:
    assert proposer_adresse("", "Jeanne", "Martin", CONNUES) == (None, "aucune")


def test_personne_sans_domaine_passe_par_linkedin() -> None:
    state = _avec("")
    personne = ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "manager", "Responsable data", "lien", {}, CONNUES)
    assert personne["canal"] == "linkedin" and personne["adresse"] == "" and personne["statut"] == "repere"


def test_adresse_lue_sur_une_source_est_citee() -> None:
    state = _avec("acme-aero.example")
    personne = ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "manager", "x", "lien", {}, CONNUES,
                                adresse="J.Martin@Acme-Aero.example")
    assert personne["adresse"] == "j.martin@acme-aero.example" and personne["confiance"] == "citée"


def test_un_refus_anterieur_ecarte_la_personne_sauf_si_on_force() -> None:
    state = _avec("vert-mer.example", "Vert Mer")
    ecartee = ajouter_personne(state, "vert-mer", "Paul", "Durand", "directeur", "x", "lien", REFUS, CONNUES)
    assert ecartee["statut"] == "ecarte" and ecartee["canal"] == "aucun" and ecartee["avertissement"]
    state2 = _avec("vert-mer.example", "Vert Mer")
    gardee = ajouter_personne(state2, "vert-mer", "Paul", "Durand", "directeur", "x", "lien", REFUS, CONNUES, forcer=True)
    assert gardee["statut"] == "repere" and gardee["canal"] == "mail"


def test_refuse_un_role_inconnu() -> None:
    state = _avec("acme-aero.example")
    with pytest.raises(ValueError):
        ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "stagiaire", "x", "lien", {}, CONNUES)


def _etat_avec_deux_personnes() -> Dict[str, Any]:
    state = _avec("inconnue.example")
    ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "manager", "x", "l1", {}, CONNUES)
    ajouter_personne(state, "acme-aero", "Paul", "Durand", "directeur", "x", "l2", {}, CONNUES)
    for personne in state["entreprises"]["acme-aero"]["personnes"]:
        personne["statut"] = "brouillon"
    return state


def test_envoi_inscrit_les_relances_a_la_date_d_envoi_reelle() -> None:
    state, suivi = _etat_avec_deux_personnes(), []
    assert marquer_envoye(state, suivi, "jeanne.martin@inconnue.example", "2026-10-17") is True
    entree = suivi[0]
    assert entree["date_j0"] == "2026-10-17" and entree["etape"] == "J+0" and entree["sequence"] == ["J+0", "J+7", "J+14"]
    assert entree["type"] == "spontanee" and entree["sans_notion"] is True and entree["prenom"] == "Jeanne"
    assert state["entreprises"]["acme-aero"]["personnes"][0]["statut"] == "envoye"


def test_un_envoi_declare_deux_fois_n_est_suivi_qu_une_fois() -> None:
    state, suivi = _etat_avec_deux_personnes(), []
    marquer_envoye(state, suivi, "jeanne.martin@inconnue.example", "2026-10-17")
    assert marquer_envoye(state, suivi, "jeanne.martin@inconnue.example", "2026-10-18") is False
    assert len(suivi) == 1


def test_adresse_inconnue_est_signalee() -> None:
    with pytest.raises(ValueError):
        marquer_envoye(_etat_avec_deux_personnes(), [], "personne@nulle-part.example", "2026-10-17")


def test_un_rebond_remet_les_collegues_aux_adresses_devinees_a_refaire() -> None:
    state = _etat_avec_deux_personnes()
    assert marquer_rebond(state, "jeanne.martin@inconnue.example") == 1
    statuts = {p["prenom"]: p["statut"] for p in state["entreprises"]["acme-aero"]["personnes"]}
    assert statuts == {"Jeanne": "rebond", "Paul": "a_refaire"}


def test_un_rebond_ne_touche_pas_les_adresses_sures() -> None:
    state = _avec("acme-aero.example")
    ajouter_personne(state, "acme-aero", "Jeanne", "Martin", "manager", "x", "l1", {}, CONNUES)
    ajouter_personne(state, "acme-aero", "Paul", "Durand", "directeur", "x", "l2", {}, CONNUES)
    assert marquer_rebond(state, "jeanne.martin@acme-aero.example") == 0


def test_aller_retour_sur_disque(tmp_path: Any) -> None:
    chemin = str(tmp_path / "prospection.json")
    state = _etat_avec_deux_personnes()
    sauver(state, chemin)
    assert charger(chemin) == state


def test_un_etat_incoherent_est_refuse_a_la_lecture(tmp_path: Any) -> None:
    chemin = tmp_path / "prospection.json"
    chemin.write_text('{"entreprises": {"x": {"slug": "autre", "ville": "Lyon", "secteur": "ia"}}}', encoding="utf-8")
    with pytest.raises(ValueError):
        charger(str(chemin))


def test_etat_et_plan_se_lisent_sans_erreur() -> None:
    state = _etat_avec_deux_personnes()
    assert lignes_etat(state)[0].startswith("1 entreprise(s), 2 personne(s)")
    assert any(ligne.startswith("Jour 1 :") for ligne in lignes_plan(state, "2026-10-15"))


def test_signature_mail_nom_d_affichage_puis_telephone() -> None:
    assert signature_mail({"nom": "Jean DUPONT", "telephone": "06 00 00 00 00"}) == "Jean Dupont\n06 00 00 00 00"
    assert signature_mail({"nom": "Jean DUPONT"}) == "Jean Dupont"


def test_une_reponse_arrete_les_relances_de_cette_personne() -> None:
    state, suivi = _etat_avec_deux_personnes(), []
    marquer_envoye(state, suivi, "jeanne.martin@inconnue.example", "2026-10-14")
    marquer_reponse(state, suivi, "jeanne.martin@inconnue.example", "fil-7")
    assert suivi[0]["etape"] == "Réponse reçue" and suivi[0]["thread_id"] == "fil-7"
    assert state["entreprises"]["acme-aero"]["personnes"][0]["statut"] == "repondu"


def test_une_reponse_a_une_adresse_inconnue_est_signalee() -> None:
    with pytest.raises(ValueError):
        marquer_reponse(_etat_avec_deux_personnes(), [], "personne@nulle-part.example")


def test_le_type_d_equipe_est_enregistre_et_controle() -> None:
    state = _etat()
    assert ajouter_entreprise(state, "Acme Aero", "Lyon", "ia", "acme-aero.example", equipe="metier")["equipe"] == "metier"
    assert ajouter_entreprise(state, "Bleu Rail", "Lyon", "ia", "bleu-rail.example")["equipe"] == "construit"
    with pytest.raises(ValueError, match="équipe"):
        ajouter_entreprise(state, "Vert Mer", "Lyon", "ia", "vert-mer.example", equipe="commerciale")
