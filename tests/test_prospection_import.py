"""Tests de l'import par lot (scripts/prospection_import.py). Entreprises et personnes fictives, aucun réseau."""
from typing import Any, Dict, List

from prospection import charger
from prospection_import import importer

CONNUES: List[Dict[str, str]] = [
    {"entreprise": "Acme Aero", "domaine": "acme-aero.example", "format": "prenom.nom", "confiance": "sûre"},
]
REFUS = {"ancien@vert-mer.example": [{"date": "2026-10-01", "source": "gmail", "extrait": "pas de poste"}]}


def _personne(prenom: str, nom: str, role: str) -> Dict[str, Any]:
    return {"prenom": prenom, "nom": nom, "role": role, "fonction": "Fonction", "linkedin": f"https://exemple.example/{prenom}"}


def _fiche(nom: str = "Acme Aero", domaine: str = "acme-aero.example", **extra: Any) -> Dict[str, Any]:
    fiche = {"nom": nom, "ville": "Lyon", "secteur": "ia", "domaine": domaine, "site": "", "cas_usage": "",
             "personnes": [_personne("Jeanne", "Martin", "manager"), _personne("Paul", "Durand", "directeur"),
                           _personne("Luc", "Petit", "chef_projet")]}
    fiche.update(extra)
    return fiche


def test_une_fiche_ajoute_l_entreprise_et_ses_trois_personnes() -> None:
    state: Dict[str, Any] = {"entreprises": {}}
    rapport = importer(state, [_fiche()], {}, CONNUES)
    assert len(state["entreprises"]["acme-aero"]["personnes"]) == 3
    assert len(rapport) == 3 and "jeanne.martin@acme-aero.example (sûre, repere)" in rapport[0]


def test_une_entreprise_en_erreur_est_retiree_en_entier_et_le_reste_passe() -> None:
    mauvaise = _fiche("Vert Mer", "vert-mer.example")
    mauvaise["personnes"][1]["role"] = "stagiaire"
    state: Dict[str, Any] = {"entreprises": {}}
    rapport = importer(state, [mauvaise, _fiche()], {}, CONNUES)
    assert "vert-mer" not in state["entreprises"] and "acme-aero" in state["entreprises"]
    assert any(ligne.startswith("REFUSÉE : Vert Mer") for ligne in rapport)


def test_une_ville_inconnue_refuse_la_fiche() -> None:
    state: Dict[str, Any] = {"entreprises": {}}
    rapport = importer(state, [_fiche(ville="Atlantide")], {}, CONNUES)
    assert state["entreprises"] == {} and rapport[0].startswith("REFUSÉE")


def test_une_fiche_sans_cle_obligatoire_est_signalee_sans_planter() -> None:
    fiche = _fiche()
    del fiche["domaine"]
    state: Dict[str, Any] = {"entreprises": {}}
    assert importer(state, [fiche], {}, CONNUES)[0].startswith("REFUSÉE")


def test_une_entreprise_deja_presente_est_ignoree() -> None:
    state: Dict[str, Any] = {"entreprises": {}}
    importer(state, [_fiche()], {}, CONNUES)
    rapport = importer(state, [_fiche(ville="Nantes")], {}, CONNUES)
    assert rapport == ["déjà présente, ignorée : Acme Aero"]
    assert state["entreprises"]["acme-aero"]["ville"] == "Lyon"


def test_un_refus_anterieur_est_signale_dans_le_rapport() -> None:
    state: Dict[str, Any] = {"entreprises": {}}
    fiche = _fiche("Vert Mer", "vert-mer.example")
    fiche["personnes"] = [dict(_personne("Marie", "Blanc", "manager"), adresse="ancien@vert-mer.example")]
    rapport = importer(state, [fiche], REFUS, CONNUES)
    assert "ecarte" in rapport[0] and "a déjà refusé" in rapport[0]


def test_l_etat_importe_se_relit_apres_sauvegarde(tmp_path: Any) -> None:
    from prospection import sauver
    state: Dict[str, Any] = {"entreprises": {}}
    importer(state, [_fiche()], {}, CONNUES)
    chemin = str(tmp_path / "p.json")
    sauver(state, chemin)
    assert charger(chemin) == state
