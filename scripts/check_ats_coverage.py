#!/usr/bin/env python3
"""Vérifie la couverture RÉELLE des mots-clés ATS dans un CV généré (N2, cf.
docs/plans/2026-09-07-plan-amelioration.md).

L'optimisation ATS actuelle (couche invisible `.ats-hidden-layer` + métadonnées PDF,
`render_cv.py`) garantit que les mots-clés de l'offre sont présents QUELQUE PART dans le
fichier — mais un mot-clé caché ne sert à rien face à un parseur ATS qui ignore ou
pénalise le texte invisible. Ce script mesure séparément la couverture dans le texte
VISIBLE (accroche, compétences, expériences, projets) et la couverture totale (visible +
couche cachée), pour repérer les offres où `cv-vars.json` (accroche, competences_ordre)
gagnerait à être retravaillé plutôt que de compter sur le seul artifice invisible.

Usage:
  python scripts/check_ats_coverage.py <slug>    # un dossier outputs/<slug>/
  python scripts/check_ats_coverage.py --all      # tous les dossiers outputs/
"""
import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR_DEFAULT: str = os.path.join(ROOT, "outputs")

VISIBLE_COVERAGE_SEUIL: float = 50.0  # % en dessous duquel on avertit


def compute_coverage(html: str, keywords: List[str]) -> Dict[str, Any]:
    """Coverage des `keywords` dans le texte visible vs. l'ensemble du document HTML."""
    soup = BeautifulSoup(html, "html.parser")
    hidden = soup.select_one(".ats-hidden-layer")
    hidden_text = hidden.get_text(" ").lower() if hidden else ""
    if hidden:
        hidden.decompose()
    visible_text = soup.get_text(" ").lower()
    full_text = visible_text + " " + hidden_text

    total = len(keywords)
    visible_hits = [k for k in keywords if k.lower() in visible_text]
    full_hits = [k for k in keywords if k.lower() in full_text]

    def pct(n: int) -> float:
        return round(100 * n / total, 1) if total else 100.0

    return {
        "total": total,
        "visible_count": len(visible_hits),
        "visible_pct": pct(len(visible_hits)),
        "full_count": len(full_hits),
        "full_pct": pct(len(full_hits)),
        "visible_missing": [k for k in keywords if k not in visible_hits],
        "missing_entirely": [k for k in keywords if k not in full_hits],
    }


def check_slug(slug: str, outputs_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    folder = os.path.join(outputs_dir or OUTPUTS_DIR_DEFAULT, slug)
    cv_vars_path = os.path.join(folder, "cv-vars.json")
    if not os.path.isfile(cv_vars_path):
        return None
    with open(cv_vars_path, "r", encoding="utf-8") as f:
        cv_vars = json.load(f)
    keywords = cv_vars.get("mots_cles_ats", [])
    if not keywords:
        return None
    html_files = [f for f in glob.glob(os.path.join(folder, "*.html")) if "CV" in os.path.basename(f)]
    if not html_files:
        return None
    with open(html_files[0], "r", encoding="utf-8") as f:
        html = f.read()
    result = compute_coverage(html, keywords)
    result["slug"] = slug
    return result


def render_report(result: Dict[str, Any]) -> str:
    icon = "✅" if result["visible_pct"] >= VISIBLE_COVERAGE_SEUIL else "⚠️"
    lines = [
        f"{icon} {result['slug']} : {result['visible_count']}/{result['total']} mots-clés visibles "
        f"({result['visible_pct']}%), {result['full_count']}/{result['total']} au total ({result['full_pct']}%)"
    ]
    if result["visible_pct"] < VISIBLE_COVERAGE_SEUIL and result["visible_missing"]:
        lines.append(f"    Absents du texte visible : {', '.join(result['visible_missing'])}")
    if result["missing_entirely"]:
        lines.append(f"    Absents même de la couche cachée (à vérifier) : {', '.join(result['missing_entirely'])}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Vérifie la couverture réelle des mots-clés ATS d'un CV généré.")
    ap.add_argument("slug", nargs="?", help="Dossier sous outputs/ à vérifier")
    ap.add_argument("--all", action="store_true", help="Vérifie tous les dossiers outputs/")
    args = ap.parse_args()

    if not args.slug and not args.all:
        sys.exit("Fournissez un slug ou --all.")

    slugs: List[str]
    if args.all:
        slugs = sorted(
            os.path.basename(d) for d in glob.glob(os.path.join(OUTPUTS_DIR_DEFAULT, "*"))
            if os.path.isdir(d) and os.path.basename(d) not in ("archives", "previews", "radar")
        )
    else:
        slugs = [args.slug]

    print("\n" + "=" * 70)
    print("COUVERTURE ATS RÉELLE (texte visible vs. couche cachée)")
    print("=" * 70 + "\n")

    checked = 0
    below_seuil = 0
    for slug in slugs:
        result = check_slug(slug)
        if result is None:
            continue
        checked += 1
        if result["visible_pct"] < VISIBLE_COVERAGE_SEUIL:
            below_seuil += 1
        print(render_report(result))

    print(f"\n{checked} dossier(s) analysé(s), {below_seuil} sous le seuil de {VISIBLE_COVERAGE_SEUIL}% visible.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
