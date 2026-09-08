#!/usr/bin/env python3
"""Construit les livrables d'UNE candidature : CV + lettre en PDF, personnalisés par offre.

Le sous-agent cv-tailor écrit d'abord deux fichiers de variables dans le dossier de l'offre :
  outputs/<slug>/cv-vars.json      (accroche, competences_ordre, projets_selection, mots_cles_ats, titre)
  outputs/<slug>/lettre-vars.json  (entreprise, poste, type, date, destinataire, objet, paragraphes)

Puis lance :
  python scripts/build_application.py --slug <slug> --profile stage|alternance

Sortie :
  outputs/<slug>/CV_<Prenom>_<NOM>.pdf
  outputs/<slug>/Lettre_<Prenom>_<NOM>.pdf
"""
import argparse
import os
import subprocess
import sys

from typing import List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from profile import doc_base_names, load_personal

PY: str = sys.executable


def run(cmd: List[str]) -> None:
    print("»", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="dossier de l'offre sous outputs/")
    ap.add_argument("--profile", choices=["stage", "alternance"], required=True)
    args = ap.parse_args()

    folder = os.path.join(ROOT, "outputs", args.slug)
    cv_vars = os.path.join(folder, "cv-vars.json")
    lettre_vars = os.path.join(folder, "lettre-vars.json")
    if not os.path.isfile(cv_vars):
        sys.exit(f"Manque {cv_vars} — cv-tailor doit l'écrire d'abord.")
    if not os.path.isfile(lettre_vars):
        sys.exit(f"Manque {lettre_vars} — cv-tailor doit l'écrire d'abord.")

    cv_base, lettre_base = doc_base_names()
    cv_html = os.path.join(folder, f"{cv_base}.html")
    lettre_html = os.path.join(folder, f"{lettre_base}.html")

    run([PY, os.path.join(ROOT, "scripts", "render_cv.py"),
         "--profile", args.profile, "--vars", cv_vars, "--out", cv_html, "--pdf"])
    run([PY, os.path.join(ROOT, "scripts", "render_lettre.py"),
         "--vars", lettre_vars, "--out", lettre_html, "--pdf"])

    cv_pdf = os.path.splitext(cv_html)[0] + ".pdf"
    lettre_pdf = os.path.splitext(lettre_html)[0] + ".pdf"
    ok = os.path.isfile(cv_pdf) and os.path.isfile(lettre_pdf)
    print("\nCV    :", cv_pdf, "OK" if os.path.isfile(cv_pdf) else "MANQUANT")
    print("Lettre:", lettre_pdf, "OK" if os.path.isfile(lettre_pdf) else "MANQUANT")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()

