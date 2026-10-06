"""Tests des filtres du réseau de contacts (scripts/network.py), sur des formes d'adresses rencontrées en vrai
(noms et entreprises fictifs)."""
import pytest

import network
from network import keep, relation_of, shareable


@pytest.fixture(autouse=True)
def my_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mon identité vient du profil local (jamais du code) : on la fixe pour les tests."""
    monkeypatch.setattr(network, "my_addresses", lambda: frozenset({"moi@exemple.fr", "moi.pro@gmail.com"}))


@pytest.mark.parametrize("address,subject,expected", [
    ("marie.durand@acme-aero.com", "Suite à notre entretien", True),
    ("camille=agence-exemple.fr@bf.eu1.r.hubspot-inbox.com", "Personnalisation des angles", False),
    ("no-reply@people-doc.com", "Bulletins de salaire", False),
    ("ami.proche@gmail.com", "Ce week-end", False),
    ("recruteur.independant@gmail.com", "Votre candidature alternance", True),
    ("moi.pro@gmail.com", "Candidature", False),
    ("MOI@exemple.fr", "Candidature", False),
])
def test_keep_only_professional_contacts(address: str, subject: str, expected: bool) -> None:
    assert keep(address, subject) is expected


@pytest.mark.parametrize("address,expected", [
    ("julien.martin@energie-exemple.com", True),
    ("prénom.nom@conseil-exemple.fr", False),
    ("groupe.dpo@industrie-exemple.com", False),
    ("image001.png@01dceddd.com", False),
    ("lucas.bernard21@gmail.com", False),
    ("lea.moreau@edu.ecole-exemple.fr", False),
    ("support_dm@stat-exemple.com", False),
])
def test_shared_contacts_are_named_people_of_a_company(address: str, expected: bool) -> None:
    assert shareable(address) is expected


def test_relation_distinguishes_human_and_automatic_replies() -> None:
    assert relation_of({"recus": 1, "auto": 0}, None) == "a répondu"
    assert relation_of({"recus": 0, "auto": 2}, None) == "réponse automatique"
    assert relation_of({"recus": 0, "auto": 0}, None) == "sans réponse"
    assert relation_of({"recus": 1, "auto": 0}, {"niveau": "bloqué", "raison": "x"}) == "a refusé"


def test_own_signature_words_come_from_the_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    network.mine_pattern.cache_clear()
    monkeypatch.setattr(network, "_personal", lambda: {"prenom": "Camille", "nom_famille": "Leroy"})
    try:
        assert network.mine_pattern().search("Camille LEROY, étudiante")
        assert not network.mine_pattern().search("Responsable recrutement")
    finally:
        network.mine_pattern.cache_clear()


def test_level_of_uses_manual_list_and_interview_domains() -> None:
    person = {"email": "rh@acme-aero.com", "sujets": ["Candidature spontanée"], "envoyes": 1, "recus": 1,
              "source": "échange"}
    assert network.level_of(person, "a répondu", set(), []) == 3
    assert network.level_of(person, "a répondu", {"acme-aero.com"}, []) == 1
    assert network.level_of(person, "a répondu", set(), ["@acme-aero.com"]) == 1
    silent = dict(person, recus=0)
    assert network.level_of(silent, "sans réponse", set(), ["@acme-aero.com"]) == 5  # un domaine seul exige une réponse


def test_notion_contact_row_carries_trust_level() -> None:
    from network_notion import CONTACT_PROPS, contact_properties
    row = {"prenom": "Marie", "nom": "Durand", "email": "marie.durand@acme-aero.com", "entreprise": "Acme Aéro",
           "fonction": "", "telephone": "", "statut": "vérifiée", "relation": "a répondu", "niveau": "Opportunité",
           "priorite": "1", "premier": "2026-09-01", "dernier": "2026-10-01", "envoyes": "2", "recus": "1",
           "sujet": "Entretien", "source": "échange", "cite_par": ""}
    props = contact_properties(row)
    assert props["Niveau de confiance"] == {"select": {"name": "Opportunité"}}
    assert props["Priorité"] == {"number": 1}
    assert "Niveau de confiance" in CONTACT_PROPS
    older = {k: v for k, v in row.items() if k not in ("niveau", "priorite")}
    assert contact_properties(older)["Priorité"] == {"number": None}
