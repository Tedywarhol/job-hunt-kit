#!/usr/bin/env python3
"""Génère la lettre de motivation (HTML puis PDF) selon le Design System index.html (Navy / Slate).

Usage:
  python scripts/render_lettre.py --vars outputs/ENTREPRISE-POSTE/lettre-vars.json \
      [--out outputs/ENTREPRISE-POSTE/Lettre_NOM_Prenom.html] [--pdf]
"""
import argparse
import html
import json
import os
import sys
from datetime import date

from typing import Any, Dict, List, Optional, Union

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from cv_labels import LANGUE_DEFAUT, fichier_donnees, libelles
from profile import date_lettre_aujourdhui, doc_base_names, ville_from_localisation
from render_cv import find_chrome, load_json, scale_css, to_pdf

LETTRE_DIR: str = os.path.join(ROOT, "templates", "lettre")


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def build_paragraphs_html(paragraphes: List[Any]) -> str:
    html_parts: List[str] = []
    for x in paragraphes:
        if isinstance(x, dict):
            if x.get("texte"):
                html_parts.append(f"<p>{esc(x['texte'])}</p>")
            if x.get("points"):
                bullets = "".join(f"<li>{esc(b)}</li>" for b in x["points"])
                html_parts.append(f"<ul>{bullets}</ul>")
        elif isinstance(x, list):
            bullets = "".join(f"<li>{esc(b)}</li>" for b in x)
            html_parts.append(f"<ul>{bullets}</ul>")
        else:
            html_parts.append(f"<p>{esc(x)}</p>")
    return "".join(html_parts)


def build_html(data: Dict[str, Any], v: Dict[str, Any]) -> str:
    lang = v.get("langue", LANGUE_DEFAUT)
    lab = libelles(lang)
    p = data["personal"]
    prof_key = v.get("type", "alternance")
    role = v.get("titre_lettre") or data["profiles"].get(prof_key, {}).get("titre_defaut", lab["role_defaut"])

    with open(os.path.join(LETTRE_DIR, "lettre.css"), "r", encoding="utf-8") as f:
        css = f.read()
    style = data.get("style", {})
    if style.get("letter_font_scale") or style.get("letter_line_height_scale"):
        css = scale_css(css, style.get("letter_font_scale", 1.0), style.get("letter_line_height_scale", 1.0))

    paras_html = build_paragraphs_html(v.get("paragraphes", []))
    objet = v.get("objet", f"Candidature : {v.get('poste', '')}")
    entreprise = v.get("entreprise", "Direction des Ressources Humaines")
    org_sub = v.get("service", "")
    org_sub_html = f'<div class="org-sub">{esc(org_sub)}</div>' if org_sub else ""

    jour = date_lettre_aujourdhui() if lang == LANGUE_DEFAUT else date.today().strftime("%B %d, %Y")
    date_str = v.get("date") or jour
    ville_candidat = v.get("ville_candidat") or ville_from_localisation(p)
    salut = esc(v.get("destinataire", lab["destinataire"]))
    cordial = esc(v["formule_finale"]) if v.get("formule_finale") else lab["formule"].format(salut=salut)
    lieu_date = lab["lieu_date"].format(ville=esc(ville_candidat), date=esc(date_str))

    return (
        f'<!DOCTYPE html><html lang="{lab["html_lang"]}"><head><meta charset="utf-8"><title>{esc(lab["lettre_titre"])} {esc(p["nom"])}</title>'
        f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">'
        f'<style>{css}</style></head><body><div class="page">'
        f'<div class="head"><div><div class="name">{esc(p["nom"])}</div><div class="role">{esc(role)}</div></div>'
        f'<div class="contact"><div><b>{esc(p["email"])}</b></div><div>{esc(p["telephone"])}</div><div>{esc(p["localisation"])}</div>'
        f'<div>{esc(p.get("linkedin", ""))}</div></div></div>'
        f'<div class="meta"><div><div class="to">{esc(entreprise)}</div>{org_sub_html}</div><div class="place">{lieu_date}</div></div>'
        f'<div class="subject-box">{esc(lab["objet"])} <span class="accent">{esc(objet)}</span></div>'
        f'<div class="body"><p class="salut">{salut},</p>{paras_html}</div>'
        f'<div class="sign"><div class="cordial">{cordial}</div>'
        f'<div class="who">{esc(p["nom"])}</div></div></div></body></html>'
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", required=True)
    ap.add_argument("--data", default=None, help="CV maître ; par défaut celui de la langue des variables")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    v: Dict[str, Any] = load_json(args.vars)
    lab = libelles(v.get("langue", LANGUE_DEFAUT))
    data_path = args.data or fichier_donnees(v.get("langue", LANGUE_DEFAUT))
    if not os.path.isfile(data_path):
        sys.exit(f"CV maître introuvable : {data_path}")
    data: Dict[str, Any] = load_json(data_path)
    p = data.get("personal", {})
    _, lettre_base = doc_base_names(p)
    out_html: str = args.out or os.path.join(ROOT, "outputs", f"{lettre_base}.html")
    os.makedirs(os.path.dirname(out_html), exist_ok=True)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(build_html(data, v))
    print("HTML:", out_html)

    if args.pdf:
        pdf_path = os.path.splitext(out_html)[0] + ".pdf"
        title = f"{lab['lettre_pdf']} - {p.get('nom', 'Candidat')}"
        author = p.get("nom", "Candidat")
        subject = f"{lab['lettre_pdf']} - {p.get('nom', '')}"
        if to_pdf(out_html, pdf_path, title=title, author=author, subject=subject):
            print("PDF:", pdf_path)


if __name__ == "__main__":
    main()
