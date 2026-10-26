"""Tests unitaires pour les moteurs de rendu HTML et PDF."""
import os
from typing import Any, Dict
import unittest.mock as mock

import pytest

from render_cv import (
    badge_etudiant,
    build_html as build_cv_html,
    build_projets_html,
    esc,
    find_chrome,
    order_competences,
    select_projets,
)
from render_lettre import (
    build_html as build_lettre_html,
    build_paragraphs_html,
)


def test_esc() -> None:
    assert esc('<div class="test">& "quote"</div>') == '&lt;div class=&quot;test&quot;&gt;&amp; &quot;quote&quot;&lt;/div&gt;'


def test_order_competences() -> None:
    items = [
        "Python (FastAPI, PySpark)",
        "SQL (PostgreSQL, BigQuery)",
        "IA & GenAI (RAG, Agents)",
        "Cloud (Docker, GCP)",
    ]
    keywords = ["ia", "cloud"]
    ordered = order_competences(items, keywords)
    assert len(ordered) == 4
    # "IA & GenAI" et "Cloud" doivent passer en tête
    assert "IA & GenAI" in ordered[0] or "Cloud" in ordered[0]


def test_select_projets(dummy_cv_data: Dict[str, Any]) -> None:
    projets = dummy_cv_data["projets"]
    selected = select_projets(projets, selection=["HR Turnover Predictor"], projets_max=1)
    assert len(selected) == 1
    assert selected[0]["titre"] == "HR Turnover Predictor"


def test_build_cv_html(dummy_cv_data: Dict[str, Any]) -> None:
    vars_data: Dict[str, Any] = {
        "titre": "Alternance Data Engineer",
        "accroche": "Profil ciblé pour l'ingénierie des données",
        "mots_cles_ats": ["Kafka", "Airflow", "PySpark"],
    }
    html = build_cv_html(dummy_cv_data, vars_data, profile="alternance")
    assert "<!DOCTYPE html>" in html
    assert "Jean DUPONT" in html
    assert "Alternance Data Engineer" in html
    assert esc("Profil ciblé pour l'ingénierie des données") in html
    assert "ats-hidden-layer" in html
    assert "Kafka" in html


def test_cv_ne_contient_aucun_tiret_cadratin(dummy_cv_data: Dict[str, Any]) -> None:
    """Règle du projet, rappelée le 2026-10-03 : jamais « — » sur un CV, ni dans les titres de projets,
    ni dans la ligne des langues, ni dans l'accroche."""
    dummy_cv_data["projets"][0]["titre"] = "Plateforme RAG — Médicale"
    dummy_cv_data["langues"] = [{"langue": "Anglais", "niveau": "Intermédiaire professionnel (B2)"}]
    html = build_cv_html(dummy_cv_data, {"accroche": "Étudiant ingénieur — data et IA"}, profile="alternance")
    assert "—" not in html
    assert "Plateforme RAG : Médicale" in html
    assert 'Anglais <span>· Intermédiaire professionnel (B2)</span>' in html


def test_experience_affiche_le_type_de_contrat(dummy_cv_data: Dict[str, Any]) -> None:
    """Retour du 2026-10-03 : les expériences étaient des stages et « ça ne se voyait nulle part »."""
    dummy_cv_data["experiences"][0]["contrat"] = "Stage"
    html = build_cv_html(dummy_cv_data, {}, profile="alternance")
    assert '<strong class="contrat">Stage</strong> · Tech Innov' in html
    dummy_cv_data["experiences"][0].pop("contrat")
    assert '<strong class="contrat">' not in build_cv_html(dummy_cv_data, {}, profile="alternance")


@pytest.mark.parametrize("badge,attendu", [
    ("Ingénieur Data & IA", "Étudiant ingénieur\nData & IA"),
    ("Ingénieur Data Science & IA", "Étudiant ingénieur\nData Science & IA"),
    ("Ingénieur & Communication", "Étudiant ingénieur\nCommunication"),
    ("ingénieur", "Étudiant ingénieur"),
    ("Étudiant ingénieur\nData Science & IA", "Étudiant ingénieur\nData Science & IA"),
    ("Data Science & IA", "Data Science & IA"),
])
def test_badge_etudiant(badge: str, attendu: str) -> None:
    """Un étudiant n'est pas encore ingénieur : le titre sous le nom ne doit jamais l'affirmer."""
    assert badge_etudiant(badge) == attendu


def test_le_titre_sous_le_nom_est_corrige_meme_si_l_offre_ecrit_ingenieur(dummy_cv_data: Dict[str, Any]) -> None:
    html = build_cv_html(dummy_cv_data, {"badge_titre": "Ingénieur Data & IA"}, profile="alternance")
    assert '<div class="badge-title">Étudiant ingénieur<br>Data &amp; IA</div>' in html


def test_select_projets_retrouve_un_titre_ecrit_avec_un_tiret_cadratin() -> None:
    """Les anciens cv-vars écrivent « A — B » alors que le CV maître écrit maintenant « A : B »."""
    projets = [{"titre": "Autre projet"}, {"titre": "HR Analytics : Modélisation prédictive du turnover"}]
    choisis = select_projets(projets, selection=["HR Analytics — Modélisation prédictive du turnover"], projets_max=1)
    assert [p["titre"] for p in choisis] == ["HR Analytics : Modélisation prédictive du turnover"]


def test_build_lettre_html(dummy_cv_data: Dict[str, Any]) -> None:
    vars_data: Dict[str, Any] = {
        "poste": "Ingénieur IA & Data",
        "entreprise": "Direction Numérique de l'État",
        "destinataire": "Madame la Directrice",
        "objet": "Candidature Alternance 24 mois",
        "paragraphes": [
            {"texte": "Premier paragraphe d'introduction."},
            {"texte": "Second paragraphe détaillant les compétences.", "points": ["Point A", "Point B"]},
        ],
    }
    html = build_lettre_html(dummy_cv_data, vars_data)
    assert "<!DOCTYPE html>" in html
    assert "Jean DUPONT" in html
    assert esc("Direction Numérique de l'État") in html
    assert "Madame la Directrice" in html
    assert "Candidature Alternance 24 mois" in html
    assert esc("Premier paragraphe d'introduction.") in html
    assert "Point A" in html


def test_find_chrome() -> None:
    chrome = find_chrome()
    # Sur l'environnement de test, Chrome ou Edge doit être détecté
    assert chrome is not None
    assert "exe" in chrome.lower()


def test_find_chrome_env_var_takes_priority() -> None:
    """CHROME_PATH doit toujours l'emporter, quel que soit l'OS."""
    with mock.patch.dict(os.environ, {"CHROME_PATH": "/chemin/perso/chrome"}):
        with mock.patch("os.path.isfile", side_effect=lambda p: p == "/chemin/perso/chrome"):
            assert find_chrome() == "/chemin/perso/chrome"


def test_find_chrome_checks_macos_paths() -> None:
    """Régression 2026-09-08 : find_chrome ne couvrait que des chemins Windows en dur —
    sur macOS/Linux frais, rien n'était détecté sans CHROME_PATH déjà connu."""
    mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CHROME_PATH", None)
        with mock.patch("sys.platform", "darwin"):
            with mock.patch("os.path.isfile", side_effect=lambda p: p == mac_path):
                assert find_chrome() == mac_path


def test_find_chrome_checks_linux_paths() -> None:
    linux_path = "/usr/bin/google-chrome"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CHROME_PATH", None)
        with mock.patch("sys.platform", "linux"):
            with mock.patch("os.path.isfile", side_effect=lambda p: p == linux_path):
                assert find_chrome() == linux_path


def _projet(titre: str, categorie: str = "") -> Dict[str, Any]:
    projet: Dict[str, Any] = {"titre": titre, "stack": "Python", "points": ["Une puce."]}
    if categorie:
        projet["categorie"] = categorie
    return projet


def test_projets_sans_categorie_gardent_la_rubrique_d_envergure() -> None:
    html = build_projets_html([_projet("A"), _projet("B")])
    assert html.count("section-title") == 1 and "Projets d&#x27;envergure" in html


def test_une_rubrique_par_categorie_dans_l_ordre_de_la_selection() -> None:
    html = build_projets_html([_projet("A", "Projets freelance"), _projet("B", "Projets personnels")])
    assert html.count("section-title") == 2 and "envergure" not in html
    assert html.index("Projets freelance") < html.index("Projets personnels")


def test_les_projets_d_un_meme_type_sont_regroupes_sous_une_seule_rubrique() -> None:
    html = build_projets_html([_projet("Alpha", "Projets freelance"), _projet("Bravo", "Projets personnels"),
                               _projet("Charlie", "Projets freelance")])
    assert html.count("Projets freelance") == 1
    rubrique_freelance = html[html.index("Projets freelance"):html.index("Projets personnels")]
    assert "Alpha" in rubrique_freelance and "Charlie" in rubrique_freelance and "Bravo" not in rubrique_freelance


def test_le_titre_d_une_rubrique_est_echappe() -> None:
    assert "&lt;b&gt;" in build_projets_html([_projet("A", "<b>Perso</b>")])


# --- Langue du CV et de la lettre (2026-10-18) -------------------------------------------------------------------

def _contenu(html: str) -> str:
    """La page sans sa feuille de style (le CSS embarqué cite « Objet », « formation-block »...)."""
    import re
    return re.sub(r"<style>.*?</style>", "", html, flags=re.S)


def test_le_cv_reste_en_francais_par_defaut(dummy_cv_data: Dict[str, Any]) -> None:
    html = build_cv_html(dummy_cv_data, {}, profile="alternance")
    assert '<html lang="fr">' in html
    assert '<div class="section-title">Compétences clés</div>' in html
    assert '<div class="section-title">Profil &amp; Adéquation</div>' in html


def test_le_cv_en_anglais_traduit_les_rubriques(dummy_cv_data: Dict[str, Any]) -> None:
    html = build_cv_html(dummy_cv_data, {"langue": "en"}, profile="alternance")
    assert '<html lang="en">' in html
    for titre in ("Education", "Key Skills", "Technical Skills", "Languages", "Interests", "Profile", "Professional Experience"):
        assert f'<div class="section-title">{titre}</div>' in html
    for francais in ("Formation", "Compétences clés", "Stack technique", "Expériences professionnelles", "Profil &amp;"):
        assert francais not in _contenu(html)


def test_les_projets_sans_categorie_prennent_le_titre_de_la_langue() -> None:
    from cv_labels import libelles
    assert "Projects</div>" in build_projets_html([_projet("A")], libelles("en"))
    assert "Projets d&#x27;envergure</div>" in build_projets_html([_projet("A")])


def test_la_couche_ats_cachee_peut_etre_desactivee(dummy_cv_data: Dict[str, Any]) -> None:
    avec = build_cv_html(dummy_cv_data, {"mots_cles_ats": ["Kafka"]}, profile="alternance")
    sans = build_cv_html(dummy_cv_data, {"mots_cles_ats": ["Kafka"], "couche_ats_cachee": False}, profile="alternance")
    assert '<div class="ats-hidden-layer">' in avec
    assert '<div class="ats-hidden-layer">' not in sans and "ATS:" not in sans


def test_les_competences_peuvent_etre_redefinies_par_offre(dummy_cv_data: Dict[str, Any]) -> None:
    html = build_cv_html(dummy_cv_data, {"competences_cles": ["Compétence propre à l'offre"]}, profile="alternance")
    assert "Compétence propre à l&#x27;offre" in html
    assert dummy_cv_data["competences_cles"][0] not in _contenu(html)


def test_les_certifications_peuvent_etre_redefinies_par_offre(dummy_cv_data: Dict[str, Any]) -> None:
    dummy_cv_data["certifications"] = ["Certificat du maître"]
    html = _contenu(build_cv_html(dummy_cv_data, {"certifications": ["Abonnement Udemy"]}, profile="alternance"))
    assert "Abonnement Udemy" in html and "Certificat du maître" not in html
    assert "Certificat du maître" in _contenu(build_cv_html(dummy_cv_data, {}, profile="alternance"))


def test_l_agrandissement_ne_touche_que_la_colonne_principale() -> None:
    from render_cv import scale_css_principale
    css = (
        "/* sidebar .main dans un commentaire */\n.sidebar .name { font-size: 10px; line-height: 1.5; }\n"
        ".skill-list li { font-size: 8px; }\n"
        ".main .section-title { font-size: 9px; }\n.exp-desc li { font-size: 8px; line-height: 1.4; }\n"
        ".project-item .project-title { font-size: 10px; }\n"
    )
    out = scale_css_principale(css, 1.5, 1.0)
    assert ".sidebar .name { font-size: 10px; line-height: 1.5; }" in out
    assert ".skill-list li { font-size: 8px; }" in out
    assert "font-size: 13.50px" in out and "font-size: 12.00px" in out and "font-size: 15.00px" in out
    assert "line-height: 1.400" in out
    assert scale_css_principale(css, 1.0, 1.0) == css
    assert "line-height: 1.500" not in out  # l'interligne de la colonne de gauche reste 1.5 tel quel
    assert "line-height: 1.540" in scale_css_principale(css, 1.0, 1.1)


def test_le_cv_peint_les_colonnes_dans_l_ordre_du_document(dummy_cv_data: Dict[str, Any]) -> None:
    """Sans cette règle, les titres de rubrique sortent avant leur contenu dans le flux du PDF (lecture ATS)."""
    assert ".sidebar > *, .main > * { position: relative; }" in build_cv_html(dummy_cv_data, {}, profile="alternance")


def test_une_langue_inconnue_est_refusee(dummy_cv_data: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Langue inconnue"):
        build_cv_html(dummy_cv_data, {"langue": "de"}, profile="alternance")


def test_le_maitre_depend_de_la_langue() -> None:
    from cv_labels import fichier_donnees
    assert fichier_donnees("fr").endswith("cv-data.json")
    assert fichier_donnees("en").endswith("cv-data.en.json")


def test_la_lettre_en_anglais(dummy_cv_data: Dict[str, Any]) -> None:
    v = {"langue": "en", "entreprise": "Acme", "objet": "Application", "date": "October 18, 2026",
         "ville_candidat": "Paris", "paragraphes": ["Hello."]}
    html = build_lettre_html(dummy_cv_data, v)
    assert '<html lang="en">' in html
    assert "Subject:" in html and "Objet" not in _contenu(html)
    assert "Paris, October 18, 2026" in html
    assert '<p class="salut">Dear Hiring Team,</p>' in html
    assert "Kind regards," in html and "agréer" not in html


def test_la_lettre_reste_en_francais_par_defaut(dummy_cv_data: Dict[str, Any]) -> None:
    v = {"entreprise": "Acme", "objet": "Candidature", "date": "18 octobre 2026", "ville_candidat": "Paris", "paragraphes": ["Bonjour."]}
    html = build_lettre_html(dummy_cv_data, v)
    assert '<html lang="fr">' in html
    assert "Objet :" in html and "Paris, le 18 octobre 2026" in html
    assert "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées." in html
