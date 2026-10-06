"""Garde-fou de tenue du CV : une page A4, avec de la marge en bas de la partie blanche.

Constat du 2026-10-03 : le gabarit coupe en silence tout ce qui dépasse (`overflow: hidden`), si bien
que le CV maître avait son dernier projet tronqué à 0,3 mm du bord de la page alors que le PDF
comptait bien « une page ». Ces tests n'appellent jamais Chrome : l'impression est simulée.
"""
import json
import os
import subprocess
import sys
import unittest.mock as mock
from typing import Any, Dict, List

import pypdf
import pytest

import build_application
import render_cv
from render_cv import (
    EXIT_TROP_CHARGE,
    MARGE_BAS_MIN_MM,
    PROJETS_MIN,
    ajuster_html,
    ajuster_projets,
    css_controle_tenue,
    tient_sur_une_page,
)


def _pdf_de(pages: int, chemin: str) -> None:
    w = pypdf.PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=595, height=842)
    with open(chemin, "wb") as f:
        w.write(f)


# ---------------------------------------------------------------- ajuster_projets (pur)

def test_ajuster_projets_garde_le_plus_grand_nombre_qui_tient() -> None:
    essais: List[int] = []

    def essayer(n: int) -> bool:
        essais.append(n)
        return n <= 3

    assert ajuster_projets(essayer, n_depart=6, n_min=2) == 3
    assert essais == [6, 5, 4, 3]  # on retire un projet à la fois, en partant du plus chargé


def test_ajuster_projets_ne_touche_a_rien_quand_ca_tient() -> None:
    assert ajuster_projets(lambda n: True, n_depart=6, n_min=2) == 6


def test_ajuster_projets_renonce_sous_le_minimum() -> None:
    essais: List[int] = []

    def jamais(n: int) -> bool:
        essais.append(n)
        return False

    assert ajuster_projets(jamais, n_depart=5, n_min=2) is None
    assert essais == [5, 4, 3, 2]  # jamais en dessous de n_min


# ---------------------------------------------------------------- variante de contrôle

def test_css_controle_tenue_reserve_la_marge_et_autorise_le_depassement() -> None:
    css = css_controle_tenue(12)
    assert css.endswith("</head>")  # remplace la balise fermante : le style est bien dans le <head>
    assert ".main{padding-bottom:12.00mm !important}" in css
    assert "overflow:visible" in css and "height:auto" in css


def test_la_marge_minimale_et_le_minimum_de_projets_sont_raisonnables() -> None:
    assert MARGE_BAS_MIN_MM >= 10  # règle du 2026-10-03 : pas moins d'un centimètre de blanc
    assert PROJETS_MIN >= 2


# ---------------------------------------------------------------- tient_sur_une_page (impression simulée)

def _html(tmp_path: Any, contenu: str = "<html><head><title>CV</title></head><body>x</body></html>") -> str:
    p = tmp_path / "cv.html"
    p.write_text(contenu, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("pages,attendu", [(1, True), (2, False)])
def test_tient_sur_une_page_suit_le_nombre_de_pages_de_la_variante(tmp_path: Any, pages: int, attendu: bool) -> None:
    html_path = _html(tmp_path)
    vu: Dict[str, str] = {}

    def faux_imprimer(chrome: str, html: str, pdf: str) -> None:
        with open(html, "r", encoding="utf-8") as f:
            vu["html"] = f.read()
        _pdf_de(pages, pdf)

    with mock.patch.object(render_cv, "find_chrome", return_value="chrome"), \
            mock.patch.object(render_cv, "_imprimer_pdf", side_effect=faux_imprimer):
        assert tient_sur_une_page(html_path, 12) is attendu

    assert ".main{padding-bottom:12.00mm !important}" in vu["html"]  # la marge exigée est bien dans la variante
    with open(html_path, "r", encoding="utf-8") as f:
        assert "controle-tenue" not in f.read()  # le vrai CV n'est jamais modifié


def test_tient_sur_une_page_inconnu_sans_chrome(tmp_path: Any) -> None:
    with mock.patch.object(render_cv, "find_chrome", return_value=None):
        assert tient_sur_une_page(_html(tmp_path)) is None


def test_tient_sur_une_page_inconnu_si_pas_de_balise_head(tmp_path: Any) -> None:
    # Sans </head> la surcharge ne s'appliquerait pas : on ne doit surtout pas répondre « ça tient ».
    with mock.patch.object(render_cv, "find_chrome", return_value="chrome"), \
            mock.patch.object(render_cv, "_imprimer_pdf") as imprimer:
        assert tient_sur_une_page(_html(tmp_path, "<p>pas de head</p>")) is None
    imprimer.assert_not_called()


def test_tient_sur_une_page_inconnu_si_l_impression_echoue(tmp_path: Any) -> None:
    with mock.patch.object(render_cv, "find_chrome", return_value="chrome"), \
            mock.patch.object(render_cv, "_imprimer_pdf", side_effect=subprocess.CalledProcessError(1, "chrome")), \
            mock.patch("logutil.log_error") as log:
        assert tient_sur_une_page(_html(tmp_path)) is None
    log.assert_called_once()  # l'échec est tracé, jamais avalé en silence


# ---------------------------------------------------------------- ajuster_html (réduction automatique)

def _data_avec_projets(dummy_cv_data: Dict[str, Any], n: int) -> Dict[str, Any]:
    data = json.loads(json.dumps(dummy_cv_data))
    data["projets"] = [
        {"titre": f"Projet numéro {i}", "stack": "Python", "points": [f"Réalisation {i}"], "impact": ""}
        for i in range(1, n + 1)
    ]
    data["variables_defaut"] = {"projets_selection": [], "projets_max": n}
    return data


def _nb_projets(chemin: str) -> int:
    with open(chemin, "r", encoding="utf-8") as f:
        return f.read().count('class="project-item"')


def _faux_controle(capacite: int):
    """Un CV « tient » si le fichier écrit contient au plus `capacite` projets."""
    return lambda chemin, marge=MARGE_BAS_MIN_MM: _nb_projets(chemin) <= capacite


def test_ajuster_html_retire_les_derniers_projets_jusqu_a_ce_que_ca_tienne(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 5)
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", side_effect=_faux_controle(3)):
        bilan = ajuster_html(data, {}, "alternance", out)
    assert bilan == {"n_depart": 5, "n": 3, "retires": ["Projet numéro 4", "Projet numéro 5"], "tient": True}
    assert _nb_projets(out) == 3  # le fichier écrit est bien la version qui tient
    with open(out, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Projet numéro 3" in html and "Projet numéro 4" not in html


def test_ajuster_html_ne_touche_a_rien_quand_ca_tient_deja(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 4)
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", side_effect=_faux_controle(10)):
        bilan = ajuster_html(data, {}, "alternance", out)
    assert bilan == {"n_depart": 4, "n": 4, "retires": [], "tient": True}


def test_ajuster_html_sans_autofit_signale_sans_rien_retirer(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 5)
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", side_effect=_faux_controle(3)):
        bilan = ajuster_html(data, {}, "alternance", out, autofit=False)
    assert bilan == {"n_depart": 5, "n": 5, "retires": [], "tient": False}
    assert _nb_projets(out) == 5


def test_ajuster_html_echoue_proprement_quand_meme_le_minimum_ne_tient_pas(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 5)
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", side_effect=_faux_controle(0)):
        bilan = ajuster_html(data, {}, "alternance", out)
    assert bilan["tient"] is False
    assert bilan["n"] == PROJETS_MIN  # on s'arrête au minimum, jamais en dessous


def test_ajuster_html_ne_boucle_pas_quand_le_controle_est_impossible(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 5)
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", return_value=None) as controle:
        bilan = ajuster_html(data, {}, "alternance", out)
    assert bilan == {"n_depart": 5, "n": 5, "retires": [], "tient": None}
    controle.assert_called_once()  # sans Chrome : un seul appel, aucune réduction à l'aveugle


def test_ajuster_html_respecte_la_selection_de_l_offre(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data = _data_avec_projets(dummy_cv_data, 5)
    v = {"projets_selection": ["Projet numéro 5", "Projet numéro 2", "Projet numéro 1"], "projets_max": 3}
    out = str(tmp_path / "cv.html")
    with mock.patch.object(render_cv, "tient_sur_une_page", side_effect=_faux_controle(2)):
        bilan = ajuster_html(data, v, "alternance", out)
    # Le projet retiré est le DERNIER de la sélection (le moins prioritaire), pas le dernier du fichier maître.
    assert bilan["retires"] == ["Projet numéro 1"]
    with open(out, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Projet numéro 5" in html and "Projet numéro 2" in html and "Projet numéro 1" not in html


# ---------------------------------------------------------------- main : codes de sortie

def _lancer_main(tmp_path: Any, dummy_cv_data: Dict[str, Any], bilan: Dict[str, Any], extra: List[str]) -> None:
    data_path = tmp_path / "cv-data.json"
    data_path.write_text(json.dumps(dummy_cv_data), encoding="utf-8")
    argv = ["render_cv.py", "--profile", "alternance", "--data", str(data_path),
            "--out", str(tmp_path / "cv.html"), "--pdf"] + extra
    with mock.patch.object(sys, "argv", argv), \
            mock.patch.object(render_cv, "ajuster_html", return_value=bilan), \
            mock.patch.object(render_cv, "to_pdf", return_value=True):
        render_cv.main()


def test_main_sort_en_code_3_quand_le_cv_est_trop_charge(tmp_path: Any, dummy_cv_data: Dict[str, Any], capsys: Any) -> None:
    bilan = {"n_depart": 6, "n": 2, "retires": [], "tient": False}
    with pytest.raises(SystemExit) as exc:
        _lancer_main(tmp_path, dummy_cv_data, bilan, [])
    assert exc.value.code == EXIT_TROP_CHARGE == 3
    assert "ne tient pas" in capsys.readouterr().err


def test_main_annonce_les_projets_retires(tmp_path: Any, dummy_cv_data: Dict[str, Any], capsys: Any) -> None:
    bilan = {"n_depart": 6, "n": 4, "retires": ["Projet A", "Projet B"], "tient": True}
    _lancer_main(tmp_path, dummy_cv_data, bilan, [])
    sortie = capsys.readouterr().out
    assert "[ajusté] 4 projet(s) sur 6" in sortie and "Projet A ; Projet B" in sortie


def test_main_previent_quand_la_tenue_n_a_pas_pu_etre_verifiee(tmp_path: Any, dummy_cv_data: Dict[str, Any], capsys: Any) -> None:
    bilan = {"n_depart": 6, "n": 6, "retires": [], "tient": None}
    _lancer_main(tmp_path, dummy_cv_data, bilan, [])  # pas d'échec : on ne bloque pas une machine sans Chrome
    assert "non vérifiée" in capsys.readouterr().err


def test_main_apercu_html_seul_ne_lance_aucun_controle(tmp_path: Any, dummy_cv_data: Dict[str, Any]) -> None:
    data_path = tmp_path / "cv-data.json"
    data_path.write_text(json.dumps(dummy_cv_data), encoding="utf-8")
    out = tmp_path / "cv.html"
    argv = ["render_cv.py", "--profile", "alternance", "--data", str(data_path), "--out", str(out)]
    with mock.patch.object(sys, "argv", argv), \
            mock.patch.object(render_cv, "tient_sur_une_page") as controle:
        render_cv.main()
    controle.assert_not_called()
    assert out.is_file()


# ---------------------------------------------------------------- build_application

def test_run_tolere_uniquement_les_codes_annonces() -> None:
    sortie_3 = [sys.executable, "-c", "import sys; sys.exit(3)"]
    assert build_application.run(sortie_3, tolere=(3,)) == 3
    with pytest.raises(subprocess.CalledProcessError):
        build_application.run(sortie_3)
    with pytest.raises(subprocess.CalledProcessError):
        build_application.run([sys.executable, "-c", "import sys; sys.exit(4)"], tolere=(3,))
    assert build_application.run([sys.executable, "-c", "pass"]) == 0
