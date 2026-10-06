#!/usr/bin/env python3
"""Contrôle de tenue des CV déjà générés : une page A4, avec de la marge en bas de la partie blanche.

Le gabarit (templates/cv/cv.css) coupe en silence tout ce qui dépasse de la page, donc un CV trop
chargé garde « une page » en perdant sa dernière puce. Pour chaque CV_*.html, on imprime une
variante jetable avec la marge exigée et on compte les pages (cf. render_cv.tient_sur_une_page).
Rapport seul : rien n'est modifié. `render_cv.py --pdf` applique déjà ce contrôle (et retire au
besoin les derniers projets) à chaque génération ; cet outil sert à auditer l'existant.

Usage :
  python scripts/check_cv_fit.py outputs/<slug>/CV_Prenom_NOM.html [autre.html ...]
  python scripts/check_cv_fit.py --all          # tous les CV_*.html sous outputs/ (environ 6 s par CV)
  python scripts/check_cv_fit.py --all --min 10
Code de sortie : 0 si tous les CV contrôlés tiennent, 1 sinon (ou si le contrôle est impossible).
"""
import argparse
import os
import sys
from typing import List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from render_cv import MARGE_BAS_MIN_MM, tient_sur_une_page  # noqa: E402


def tous_les_cv_html() -> List[str]:
    out: List[str] = []
    for dossier, _, fichiers in os.walk(os.path.join(ROOT, "outputs")):
        out += [os.path.join(dossier, f) for f in fichiers if f.startswith("CV_") and f.lower().endswith(".html")]
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="*", help="CV au format HTML (celui qui a produit le PDF)")
    ap.add_argument("--all", action="store_true", help="tous les CV_*.html sous outputs/")
    ap.add_argument("--min", type=float, default=MARGE_BAS_MIN_MM,
                    help=f"blanc minimal sous le dernier élément, en mm (défaut {MARGE_BAS_MIN_MM:.0f})")
    args = ap.parse_args()

    cibles = list(args.html) + (tous_les_cv_html() if args.all else [])
    if not cibles:
        ap.error("indique au moins un CV HTML, ou --all")

    echecs = 0
    for chemin in cibles:
        verdict = tient_sur_une_page(chemin, args.min)
        etat = {True: "OK     ", False: "TROP    ", None: "INCONNU "}[verdict]
        echecs += verdict is not True
        nom = os.path.relpath(chemin, ROOT) if chemin.startswith(ROOT) else chemin
        print(f"{etat}{nom}", flush=True)
    print(f"\n{len(cibles) - echecs}/{len(cibles)} CV tiennent sur une page A4 avec {args.min:.0f} mm de blanc en bas.")
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
