"""Tests d'intégration pour la CLI hunt.py."""
import os
import shutil
import subprocess
import sys
from typing import Any

PY: str = sys.executable


def test_hunt_help() -> None:
    res = subprocess.run([PY, "hunt.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Job-Hunt Kit" in res.stdout
    assert "status" in res.stdout
    assert "apply" in res.stdout
    assert "kit" in res.stdout
    assert "test" in res.stdout


def test_hunt_status() -> None:
    res = subprocess.run([PY, "hunt.py", "status"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "JOB-HUNT KIT" in res.stdout
    assert "Candidat actif" in res.stdout
    assert "Moteur PDF" in res.stdout


def test_hunt_cv_preview() -> None:
    # Génération d'un CV en HTML/PDF de prévisualisation
    res = subprocess.run([PY, "hunt.py", "cv", "--profile", "alternance"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "HTML:" in res.stdout


def test_slugify() -> None:
    from hunt import slugify
    assert slugify("Doctolib — Data Scientist (Alternance 24m)") == "doctolib-data-scientist-alternance-24m"
    assert slugify("Équipe R&D & IA — Paris 75000") == "equipe-rd-ia-paris-75000"


def test_load_available_opportunities() -> None:
    from hunt import load_available_opportunities
    opps = load_available_opportunities()
    assert isinstance(opps, list)


def test_create_application_scaffolding() -> None:
    from hunt import create_application_scaffolding
    target = create_application_scaffolding("test-slug-ux", "TestCorp", "Data Lead", "alternance")
    try:
        assert os.path.isdir(target)
        assert os.path.isfile(os.path.join(target, "cv-vars.json"))
        assert os.path.isfile(os.path.join(target, "lettre-vars.json"))
    finally:
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)


def test_profile_import_extracts_text(tmp_path: Any) -> None:
    src = os.path.join(str(tmp_path), "cv.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write("Jean Dupont — Data Analyst\nExpérience chez Acme (2023-2025)")

    res = subprocess.run([PY, "hunt.py", "profile", "import", src], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Texte extrait" in res.stdout
    assert "/import-profile" in res.stdout

    out_path = os.path.join("state", "import-source.txt")
    assert os.path.isfile(out_path)
    with open(out_path, "r", encoding="utf-8") as f:
        assert "Jean Dupont" in f.read()


def test_profile_import_missing_file() -> None:
    res = subprocess.run([PY, "hunt.py", "profile", "import", "does-not-exist.pdf"], capture_output=True, text=True)
    assert res.returncode == 1
    assert "introuvable" in res.stdout


def test_create_application_scaffolding_stores_offer_link() -> None:
    """M6 (audit 2026-09-07) : le lien d'offre, quand connu, doit être tracé dans
    lettre-vars.json pour que check_consistency.py puisse relier le dossier à Notion."""
    from hunt import create_application_scaffolding
    import json as json_module
    target = create_application_scaffolding("test-slug-lien", "TestCorp", "Data Lead", "alternance", lien="https://example.com/offre/123")
    try:
        with open(os.path.join(target, "lettre-vars.json"), "r", encoding="utf-8") as f:
            lv = json_module.load(f)
        assert lv["lien"] == "https://example.com/offre/123"
    finally:
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
