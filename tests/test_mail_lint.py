"""Tests des contrôles de langue des mails de prospection (scripts/mail_lint.py, retour du 2026-10-12)."""
from typing import List

from mail_lint import fautes_orthographe, normaliser_typographie, phrases_communes, verifier_langue


class FauxDictionnaire:
    """Dictionnaire qui ne connaît que les mots donnés (évite de dépendre de pyspellchecker)."""

    def __init__(self, connus: List[str]) -> None:
        self.connus = set(connus)

    def unknown(self, mots: List[str]) -> List[str]:
        return [m for m in mots if m not in self.connus]


def test_signale_l_adjectif_rattache_a_l_alternance() -> None:
    mail = "Je recherche une alternance de vingt-quatre mois en Data Science, disponible immédiatement, en rythme 3/3."
    assert any("adjectif mal rattaché" in r for r in verifier_langue(mail))


def test_accepte_la_disponibilite_rattachee_au_candidat() -> None:
    mail = "Je suis disponible immédiatement et je recherche une alternance de vingt-quatre mois en Data Science."
    assert verifier_langue(mail) == []


def test_signale_un_tic_repete() -> None:
    mail = "Je me permets de vous écrire. Je me permets aussi de vous joindre mon CV."
    assert any("je me permets" in r and "2 fois" in r for r in verifier_langue(mail))


def test_tolere_un_tic_utilise_une_fois() -> None:
    assert verifier_langue("Je me permets de vous écrire au sujet de votre annonce.") == []


def test_signale_le_parallelisme_et_le_pronom_ambigu() -> None:
    mail = "L'IA est bien plus qu'un sujet d'études pour moi. Son message m'a orienté vers vous."
    remarques = " ".join(verifier_langue(mail))
    assert "bien plus qu'un" in remarques
    assert "son message m'a" in remarques


def test_signale_la_typographie_et_les_ligatures() -> None:
    remarques = " ".join(verifier_langue("Ce poste me tient à coeur  vraiment , merci d'avoir répondu."))
    assert "espaces doubles" in remarques
    assert "espace avant une virgule" in remarques
    assert "ligature manquante" in remarques


def test_signale_l_espace_ordinaire_ou_absente_avant_la_ponctuation_haute() -> None:
    ordinaire = " ".join(verifier_langue("Auriez-vous quinze minutes ? Merci."))
    collee = " ".join(verifier_langue("Auriez-vous quinze minutes? Merci."))
    assert "espace ordinaire avant" in ordinaire
    assert "aucune espace avant" in collee


def test_accepte_la_ponctuation_haute_avec_espace_insecable() -> None:
    mail = "Auriez-vous quinze\xa0minutes\xa0? Voici l’objet\xa0: «\xa0une idée\xa0». Rendez-vous à 14:00 sur https://exemple.fr/a?b=1\xa0!"
    assert [r for r in verifier_langue(mail) if "espace" in r] == []


def test_signale_les_guillemets_sans_espace_insecable() -> None:
    assert any("guillemets" in r for r in verifier_langue("Votre post « une idée » m’a plu."))


def test_signale_la_formule_finale_collee_au_paragraphe() -> None:
    colle = "Merci pour votre temps.\nBien cordialement,\nTedy"
    separe = "Merci pour votre temps.\n\nBien cordialement,\nTedy"
    assert any("ligne vide avant la formule" in r for r in verifier_langue(colle))
    assert not any("ligne vide avant la formule" in r for r in verifier_langue(separe))


def test_normalise_la_typographie_puis_ne_signale_plus_rien() -> None:
    brut = "Bonjour Anne,\n\nVotre post « une idée » m'a plu , vraiment. Auriez-vous quinze minutes ?\n\nMerci d'avance.  Bonne journée.\n\nBien cordialement,\nTedy"
    propre = normaliser_typographie(brut)
    assert verifier_langue(propre) == []
    assert normaliser_typographie(propre) == propre
    assert "m’a plu," in propre and "\xa0?" in propre


def test_normalisation_laisse_les_liens_et_les_heures_intacts() -> None:
    texte = "Voir https://exemple.fr/a?b=1:2 ou ecrire a anne@exemple.fr vers 14:00."
    assert normaliser_typographie(texte) == texte


def test_ne_lit_pas_une_adresse_comme_une_faute_d_espacement() -> None:
    assert verifier_langue("Écrivez-moi à tedy.nom@exemple.fr ou sur https://exemple.fr/a,b pour échanger.") == []


def test_trouve_la_phrase_recopiee_entre_deux_mails() -> None:
    commune = "Je vous remercie sincèrement pour le temps que vous voudrez bien consacrer à ma demande."
    mails = {"a": f"Bonjour Anne,\n\n{commune}\n\nBien cordialement", "b": f"Bonjour Paul,\n\n{commune}\n\nCordialement"}
    trouvees = phrases_communes(mails)
    assert len(trouvees) == 1
    assert trouvees[0][2].startswith("Je vous remercie sincèrement")


def test_une_phrase_repliee_sur_deux_lignes_reste_une_phrase() -> None:
    repliee = "Je vous remercie sincèrement pour le temps que vous voudrez\nbien consacrer à ma demande."
    droite = "Je vous remercie sincèrement pour le temps que vous voudrez bien consacrer à ma demande."
    assert len(phrases_communes({"a": repliee, "b": droite})) == 1


def test_ignore_la_signature_et_les_phrases_courtes() -> None:
    signature = "\n\nBien cordialement,\n\nJeanne DUPONT, étudiante ingénieure Data Science et IA, joignable partout"
    mails = {"a": "Bonjour Anne, mon CV est joint." + signature, "b": "Bonjour Paul, mon CV est joint." + signature}
    assert phrases_communes(mails) == []


def test_ne_confond_pas_deux_mails_differents() -> None:
    mails = {
        "a": "Bonjour Anne, votre équipe travaille sur des assistants à base de modèles de langage pour la santé.",
        "b": "Bonjour Paul, merci pour le créneau de jeudi à quatorze heures, il me convient parfaitement.",
    }
    assert phrases_communes(mails) == []


def test_orthographe_ignore_les_noms_propres_et_les_adresses() -> None:
    dico = FauxDictionnaire(["bonjour", "merci", "pour", "votre", "réponse"])
    texte = "Bonjour Jeanne, merci pour votre réponse, écrivez à jeanne.martin@acme-aero.example mais pas à quelqu'un d'autre."
    fautes = fautes_orthographe(texte, dico)
    assert "jeanne" not in fautes and "acme" not in fautes
    assert "écrivez" in fautes


def test_orthographe_signale_un_mot_inconnu() -> None:
    assert fautes_orthographe("votre responce est arrivée", FauxDictionnaire(["votre", "est", "arrivée"])) == ["responce"]
