#!/usr/bin/env python3
"""Checklist outillée de ton humain pour lettres/emails (N1, cf. plan d'amélioration).

Les agents `cv-tailor` et `recruiter-outreach` référençaient un skill "humanizer" qui
n'existe pas dans cet environnement — la consigne « ton naturel, pas de formules creuses »
restait donc déclarative, sans rien pour la vérifier. Ce script ne remplace pas un
relecteur humain, mais donne un filet de sécurité déterministe et gratuit (aucun appel
LLM) sur les deux points les plus concrets déjà exigés ailleurs dans le projet :
  1. Caractères interdits : « — » (tiret cadratin) et « & » (le formulaire encode &amp;).
  2. Formules creuses fréquentes dans un texte généré par IA — signalées pour relecture,
     jamais bloquantes (une expression légitime peut apparaître dans un contexte correct).

Usage:
  python scripts/check_human_tone.py outputs/<slug>/lettre-vars.json
  python scripts/check_human_tone.py --text "corps d'email à vérifier"
"""
import argparse
import json
import re
import sys
from typing import Any, Dict, List

FORBIDDEN_CHARS: Dict[str, str] = {
    "—": "tiret cadratin — remplacer par une virgule, un point, ou reformuler",
    "&": "esperluette — le formulaire l'encode en &amp; ; écrire « et »",
}

# Formules creuses fréquentes dans un texte généré par IA — heuristique, pas une liste
# exhaustive. Signalé pour relecture, jamais une raison de rejet automatique.
FORMULES_CREUSES: List[str] = [
    "je suis convaincu que mon profil",
    "je suis convaincue que mon profil",
    "correspond parfaitement à vos attentes",
    "n'hésitez pas à me contacter pour de plus amples informations",
    "riche d'une expérience",
    "fort de mes compétences",
    "forte de mes compétences",
    "je n'ai aucun doute",
    "je suis persuadé que",
    "je suis persuadée que",
]


def check_text(text: str) -> Dict[str, Any]:
    """Analyse un texte : caractères interdits présents, formules creuses détectées."""
    chars_found = [c for c in FORBIDDEN_CHARS if c in text]
    t_lower = text.lower()
    formules_found = [f for f in FORMULES_CREUSES if f in t_lower]
    return {
        "chars_interdits": chars_found,
        "formules_creuses": formules_found,
        "ok": not chars_found and not formules_found,
    }


def extract_texts_from_lettre_vars(data: Dict[str, Any]) -> List[str]:
    """Aplati les paragraphes de lettre-vars.json (str, dict{texte,points}, ou liste de puces)."""
    texts: List[str] = []
    for p in data.get("paragraphes", []):
        if isinstance(p, str):
            texts.append(p)
        elif isinstance(p, dict):
            if p.get("texte"):
                texts.append(p["texte"])
            texts.extend(p.get("points", []))
        elif isinstance(p, list):
            texts.extend(p)
    if data.get("objet"):
        texts.append(data["objet"])
    return texts


def render_report(label: str, result: Dict[str, Any]) -> str:
    if result["ok"]:
        return f"  ✅ {label}"
    lines = [f"  ⚠️  {label}"]
    if result["chars_interdits"]:
        for c in result["chars_interdits"]:
            lines.append(f"      caractère interdit « {c} » : {FORBIDDEN_CHARS[c]}")
    if result["formules_creuses"]:
        for f in result["formules_creuses"]:
            lines.append(f"      formule creuse à relire : « {f} »")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Checklist de ton humain pour lettres/emails.")
    ap.add_argument("path", nargs="?", help="Fichier lettre-vars.json à vérifier")
    ap.add_argument("--text", help="Texte brut à vérifier directement (ex. corps d'email)")
    args = ap.parse_args()

    if not args.path and not args.text:
        sys.exit("Fournissez un fichier lettre-vars.json ou --text \"...\".")

    print("\n" + "=" * 60)
    print("CHECKLIST TON HUMAIN")
    print("=" * 60 + "\n")

    all_ok = True
    if args.text:
        result = check_text(args.text)
        all_ok = result["ok"]
        print(render_report("(texte fourni)", result))
    else:
        with open(args.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        texts = extract_texts_from_lettre_vars(data)
        if not texts:
            sys.exit(f"Aucun paragraphe trouvé dans {args.path}.")
        for i, t in enumerate(texts, 1):
            result = check_text(t)
            all_ok = all_ok and result["ok"]
            print(render_report(f"paragraphe {i}", result))

    print("\n" + ("✅ Rien à signaler." if all_ok else "⚠️  Points à relire ci-dessus (avertissement, pas un blocage)."))
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
