"""Tests de scripts/prospection_gmail.py : contrôle du lot, brouillons, détection des envois et des rebonds.

Le service Gmail est simulé ; aucun brouillon ni envoi réel. Entreprises et personnes fictives.
"""
import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import unittest.mock as mock

import pytest

import prospection_gmail as pg
from prospection_gmail import (
    a_rebondi, creer_brouillons, dernier_envoi, detecter, lire_lot, pieces_jointes, problemes_mail, verifier_lot,
)

ADRESSE = "jeanne.martin@acme-aero.example"
MILLIS_2026_10_17 = 1792238400000  # 2026-10-17 en début d'après-midi, loin d'un changement de jour dans tout fuseau


def _service(messages: Optional[List[Dict[str, str]]] = None, date_ms: int = MILLIS_2026_10_17) -> mock.MagicMock:
    service = mock.MagicMock()
    messages_api = service.users.return_value.messages.return_value
    messages_api.list.return_value.execute.return_value = {"messages": messages or []}
    messages_api.get.return_value.execute.return_value = {"internalDate": str(date_ms)}
    return service


def _etat(statut: str = "repere", confiance: str = "devinée", **extra: Any) -> Dict[str, Any]:
    personne = {"prenom": "Jeanne", "nom": "Martin", "role": "manager", "fonction": "x", "linkedin": "l",
                "adresse": ADRESSE, "confiance": confiance, "canal": "mail", "statut": statut, **extra}
    entreprise = {"slug": "acme-aero", "nom": "Acme Aero", "ville": "Lyon", "secteur": "ia",
                  "domaine": "acme-aero.example", "personnes": [personne]}
    return {"entreprises": {"acme-aero": entreprise}}


@pytest.fixture(autouse=True)
def dossier_outputs(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(pg, "ROOT", str(tmp_path))
    monkeypatch.setattr(pg, "doc_base_names", lambda: ("CV_Jean_DUPONT", "Lettre_Jean_DUPONT"))
    monkeypatch.setattr(pg.contact_guard, "load_refusals", lambda: {})
    monkeypatch.setattr(pg.prospection, "sauver", lambda *_: None)
    return tmp_path


def _ajouter_pieces(racine: Any) -> None:
    dossier = racine / "outputs" / "acme-aero"
    dossier.mkdir(parents=True)
    for nom in ("CV_Jean_DUPONT.pdf", "Lettre_Jean_DUPONT.pdf"):
        (dossier / nom).write_bytes(b"%PDF")


def _mail(**o: str) -> Dict[str, str]:
    return {"entreprise": "acme-aero", "adresse": ADRESSE, "objet": "Alternance en IA", "corps": "Bonjour Jeanne", **o}


def test_lire_lot_refuse_un_lot_vide_ou_incomplet(tmp_path: Any) -> None:
    chemin = tmp_path / "lot.json"
    chemin.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        lire_lot(str(chemin))
    chemin.write_text(json.dumps([{"entreprise": "x", "adresse": "a@b.example", "objet": "", "corps": "c"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="objet"):
        lire_lot(str(chemin))


def test_pieces_jointes_pointent_le_dossier_de_l_entreprise(dossier_outputs: Any) -> None:
    assert [os.path.basename(p) for p in pieces_jointes("acme-aero")] == ["CV_Jean_DUPONT.pdf", "Lettre_Jean_DUPONT.pdf"]


def test_dernier_envoi_lit_la_date_du_message_envoye() -> None:
    assert dernier_envoi(_service([{"id": "m1"}]), ADRESSE) == "2026-10-17"


def test_dernier_envoi_aucun_message() -> None:
    assert dernier_envoi(_service(), ADRESSE) is None


def test_dernier_envoi_cherche_dans_tous_les_fils_envoyes() -> None:
    service = _service()
    dernier_envoi(service, ADRESSE, "2026-10-15")
    requete = service.users.return_value.messages.return_value.list.call_args.kwargs["q"]
    assert requete == f"in:sent to:{ADRESSE} after:2026/10/15"


def test_a_rebondi_cherche_un_message_d_erreur_de_remise() -> None:
    assert a_rebondi(_service([{"id": "r"}]), ADRESSE, "2026-10-17") is True
    assert a_rebondi(_service(), ADRESSE, "2026-10-17") is False


def test_un_lot_sain_n_a_aucun_probleme(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    assert problemes_mail(_mail(), _etat(), {}, _service()) == []


def test_signale_un_mail_deja_envoye_dans_un_autre_fil(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    problemes = problemes_mail(_mail(), _etat(), {}, _service([{"id": "m"}]))
    assert any("déjà été envoyé le 2026-10-17" in p for p in problemes)


def test_signale_un_refus_anterieur(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    refus = {ADRESSE: [{"date": "2026-10-01", "source": "gmail", "extrait": "pas de poste"}]}
    assert any("garde-fou" in p for p in problemes_mail(_mail(), _etat(), refus, _service()))


def test_signale_des_pieces_jointes_absentes() -> None:
    assert any("pièces jointes absentes" in p for p in problemes_mail(_mail(), _etat(), {}, _service()))


def test_signale_une_adresse_hors_etat_et_un_statut_inattendu(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    assert problemes_mail(_mail(adresse="inconnu@nulle-part.example"), _etat(), {}, _service())
    assert any("statut envoye" in p for p in problemes_mail(_mail(), _etat(statut="envoye"), {}, _service()))


def test_le_lot_est_refuse_en_entier_si_une_adresse_est_en_double(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    with mock.patch.object(pg.check_human_tone, "rapport_lot", return_value=True):
        problemes = verifier_lot([_mail(), _mail(corps="Autre texte")], _etat(), _service(), False)
    assert any("présente deux fois" in p for p in problemes)


def test_le_controle_de_ton_peut_bloquer_le_lot(dossier_outputs: Any) -> None:
    _ajouter_pieces(dossier_outputs)
    with mock.patch.object(pg.check_human_tone, "rapport_lot", return_value=False):
        assert any("Contrôle de ton" in p for p in verifier_lot([_mail()], _etat(), _service(), False))


@mock.patch("prospection_gmail.load_personal", return_value={"email": "jean.dupont@test.example"})
@mock.patch("prospection_gmail.create_draft", return_value={"id": "brouillon-9"})
def test_creer_brouillons_enregistre_l_etat_et_joint_cv_et_lettre(creer: mock.MagicMock, _: mock.MagicMock) -> None:
    state = _etat()
    assert creer_brouillons([_mail()], state, mock.MagicMock()) == 1
    personne = state["entreprises"]["acme-aero"]["personnes"][0]
    assert personne["statut"] == "brouillon" and personne["brouillon_id"] == "brouillon-9"
    assert personne["objet"] == "Alternance en IA" and personne["date_brouillon"] == date.today().isoformat()
    assert len(creer.call_args.kwargs["attachment_paths"]) == 2


def test_detecter_un_envoi_l_inscrit_pour_les_relances() -> None:
    state, suivi = _etat(statut="brouillon", date_brouillon="2026-10-15", objet="Alternance en IA"), []
    rapport = detecter(state, _service([{"id": "m"}]), suivi, appliquer=True)
    assert rapport == [f"Envoyé le 2026-10-17 : {ADRESSE}"]
    assert suivi[0]["date_j0"] == "2026-10-17" and state["entreprises"]["acme-aero"]["personnes"][0]["statut"] == "envoye"


def test_detecter_sans_appliquer_ne_modifie_rien() -> None:
    state, suivi = _etat(statut="brouillon", date_brouillon="2026-10-15"), []
    detecter(state, _service([{"id": "m"}]), suivi, appliquer=False)
    assert suivi == [] and state["entreprises"]["acme-aero"]["personnes"][0]["statut"] == "brouillon"


def test_detecter_un_rebond_de_sonde_recente() -> None:
    hier = (date.today() - timedelta(days=1)).isoformat()
    state = _etat(statut="envoye", date_envoi=hier)
    assert detecter(state, _service([{"id": "r"}]), [], appliquer=True) == [f"REBOND : {ADRESSE}"]
    assert state["entreprises"]["acme-aero"]["personnes"][0]["statut"] == "rebond"


def test_pas_de_recherche_de_rebond_pour_une_adresse_sure_ou_ancienne() -> None:
    hier = (date.today() - timedelta(days=1)).isoformat()
    service = _service([{"id": "r"}])
    assert detecter(_etat(statut="envoye", confiance="sûre", date_envoi=hier), service, [], True) == []
    ancien = (date.today() - timedelta(days=10)).isoformat()
    assert detecter(_etat(statut="envoye", date_envoi=ancien), service, [], True) == []
    service.users.return_value.messages.return_value.list.assert_not_called()


def _ecrire_lot(dossier: Any, corps: str) -> str:
    fichier = dossier / "lot.json"
    contenu = [{"entreprise": "acme-aero", "adresse": ADRESSE, "objet": "Objet", "corps": corps}]
    fichier.write_text(json.dumps(contenu), encoding="utf-8")
    return str(fichier)


def test_le_lot_est_signe_au_chargement(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "load_personal", lambda: {"nom": "Jean DUPONT", "telephone": "06 00 00 00 00"})
    lot = lire_lot(_ecrire_lot(tmp_path, "Bonjour,\n\nBien cordialement,\n{signature}"))
    assert lot[0]["corps"].endswith("Bien cordialement,\nJean Dupont\n06 00 00 00 00")


def test_le_lot_recoit_la_typographie_francaise_au_chargement(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "load_personal", lambda: {"nom": "Jean DUPONT"})
    lot = lire_lot(_ecrire_lot(tmp_path, "Bonjour,\n\nAuriez-vous quinze minutes ? C'est l'idée.\n\nBien cordialement,\n{signature}"))
    assert "minutes\xa0?" in lot[0]["corps"]
    assert "C’est l’idée" in lot[0]["corps"]


def test_un_champ_oublie_bloque_le_lot(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "load_personal", lambda: {"nom": "Jean DUPONT"})
    with pytest.raises(ValueError, match="pas rempli"):
        lire_lot(_ecrire_lot(tmp_path, "Bonjour {Prénom},\n{signature}"))
