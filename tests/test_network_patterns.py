"""Tests des règles du réseau de contacts (scripts/network_patterns.py), sur des formes réelles de noms et d'adresses
(noms, entreprises et numéros fictifs)."""
import pytest

from network_patterns import (
    best_format,
    build_address,
    detect_format,
    extract_phone,
    extract_title,
    signature_block,
    split_name,
)


@pytest.mark.parametrize("display,email,expected", [
    ("DURAND Marie", "marie.durand@acme-aero.com", ("Marie", "Durand")),
    ("RAKOTO Hery (ACME ELECTRICAL & POWER)", "hery.rakoto@acme-aero.com", ("Hery", "Rakoto")),
    ("Rossi, Marco", "marco.rossi@auto-exemple.com", ("Marco", "Rossi")),
    ("Julien MOREAU", "julien.moreau@luxe-exemple.com", ("Julien", "Moreau")),
    ("Thomas Petit", "thomas.petit@immo-exemple.fr", ("Thomas", "Petit")),
    ("Laura BLANC - Exemplia", "laura.blanc@exemplia.teamtailor-mail.com", ("Laura", "Blanc")),
    ("Claire de Villiers", "cdevilliers@mode-exemple.com", ("Claire", "de Villiers")),
    ("", "pierre.garnier@ia-exemple.com", ("Pierre", "Garnier")),
    ("Recrutement Banque", "humanresources@banque-exemple.com", ("", "")),
    ("", "careers@sante-exemple.com", ("", "")),
])
def test_split_name(display: str, email: str, expected: tuple) -> None:
    assert split_name(display, email) == expected


@pytest.mark.parametrize("email,first,last,fmt", [
    ("marie.durand@acme-aero.com", "Marie", "Durand", "prenom.nom"),
    ("vmartin@cosmetique-exemple.com", "Valérie", "Martin", "pnom"),
    ("cdevilliers@mode-exemple.com", "Claire", "de Villiers", "pnom"),
    ("t.lambert@joaillerie-exemple.com", "Thomas", "Lambert", "p.nom"),
    ("anne-sophie.richard@ministere-exemple.gouv.fr", "Anne-Sophie", "Richard", "prenom.nom"),
    ("david@papeterie-exemple.fr", "David", "Martin", "prenom"),
    ("recrutement@groupe-exemple.com", "", "", None),
])
def test_detect_format(email: str, first: str, last: str, fmt: str) -> None:
    assert detect_format(email, first, last) == fmt


def test_build_address_strips_accents_and_particles() -> None:
    assert build_address("prenom.nom", "Hélène", "Ségur", "exemple.fr") == "helene.segur@exemple.fr"
    assert build_address("pnom", "Claire", "de Villiers", "mode-exemple.com") == "cdevilliers@mode-exemple.com"
    assert build_address("prenom.nom", "", "Lefèvre", "exemple.fr") is None


def test_best_format_weighs_evidence() -> None:
    assert best_format([("prenom.nom", "vérifiée"), ("pnom", "délivrée")]) == ("prenom.nom", "sûre")
    assert best_format([("prenom.nom", "délivrée")]) == ("prenom.nom", "probable")
    assert best_format([("prenom.nom", "invalide")]) == (None, "inconnue")
    assert best_format([]) == (None, "inconnue")


def test_signature_phone_and_title() -> None:
    body = (
        "Bonjour Camille,\net merci de votre intérêt.\nBonne journée,\n\nAntoine LEROY\nCTO | Plateforme\n"
        "+33 6 00 00 00 01\nExemple Climat\n\nLe lun. 5 oct. 2026, Camille a écrit :\n> Tél : 06 11 22 33 44"
    )
    block = signature_block(body, "Antoine", "Leroy")
    assert extract_phone(block) == "+33 6 00 00 00 01"
    assert extract_title(block) == "CTO | Plateforme"


def test_international_phone_and_no_phone() -> None:
    assert extract_phone("Mobile: +39 300 0000000") == "+39 300 0000000"
    assert extract_phone("Pas de numéro ici, seulement 2026.") == ""


def test_summarize_domains_prefers_verified_and_lists_invalid() -> None:
    from network_patterns import address_status, summarize_domains
    people = [
        {"email": "marie.durand@acme-aero.com", "prenom": "Marie", "nom": "Durand", "entreprise": "Acme Aéro",
         "statut": address_status("x", 1, 2, False, False)},
        {"email": "sophie.bernard@acme-aero.com", "prenom": "Sophie", "nom": "Bernard", "entreprise": "Acme Aéro",
         "statut": address_status("x", 1, 0, False, False)},
        {"email": "careers@sante-exemple.com", "prenom": "", "nom": "", "entreprise": "Santé Exemple",
         "statut": address_status("x", 1, 0, True, False)},
    ]
    rows = {r["domaine"]: r for r in summarize_domains(people)}
    assert rows["acme-aero.com"]["format"] == "prenom.nom"
    assert rows["acme-aero.com"]["confiance"] == "sûre"
    assert rows["sante-exemple.com"]["format"] == ""
    assert rows["sante-exemple.com"]["invalides"] == "careers@sante-exemple.com"
    assert rows["sante-exemple.com"]["generiques"] == "careers@sante-exemple.com"


@pytest.mark.parametrize("subjects,sent,received,relation,shared,in_process,free_mail,manual,expected", [
    ("Suite à notre entretien", 1, 1, "a répondu", False, False, False, False, 1),
    ("Invitation Zoom", 1, 0, "sans réponse", False, True, False, False, 1),
    ("Candidature spontanée", 2, 1, "a répondu", False, True, False, False, 1),
    ("Suite à notre entretien", 1, 1, "a répondu", False, False, True, False, 3),
    ("Candidature spontanée", 1, 0, "sans réponse", False, False, False, True, 1),
    ("Candidature spontanée", 0, 0, "sans réponse", True, False, False, False, 2),
    ("Candidature spontanée", 1, 1, "a refusé", False, False, False, False, 4),
    ("Relance", 2, 1, "a répondu", False, False, False, False, 2),
    ("Candidature spontanée", 1, 1, "a répondu", False, False, False, False, 3),
    ("Candidature spontanée", 3, 0, "réponse automatique", False, False, False, False, 5),
])
def test_trust_level_orders_contacts_from_warm_to_cold(subjects: str, sent: int, received: int, relation: str,
                                                       shared: bool, in_process: bool, free_mail: bool, manual: bool,
                                                       expected: int) -> None:
    from network_patterns import trust_level
    assert trust_level(subjects, sent, received, relation, shared, in_process, free_mail, manual) == expected
