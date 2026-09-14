#!/usr/bin/env python3
"""Génère le package zippé prêt à être partagé : 'job-hunt-kit_<date>.zip'.

Exclut strictement :
- Tous les secrets (config/.notion_token, config/credentials.json, config/gmail_token.json, .env)
- Les dossiers de runtime (outputs/, logs/, state/ [sauf .gitkeep])
- Les caches et fichiers locaux (__pycache__, .claude/settings.local.json, .zcode/, etc.)
- Les données personnelles dans cv-data.json / cv-data.en.json / notion.json (remplacés par les .template)
- Les artefacts personnels/datés non génériques : index.html (page statique non paramétrée),
  docs/plans/2026-09-07-*.md (audit daté), config/apply-routine-schedule-prompt.md (routine
  liée au compte de l'utilisateur) — cf. décision du 2026-09-08.

Audit après coup : scanne le contenu de TOUS les fichiers texte inclus (pas seulement
cv-data.json) pour l'email/téléphone réel chargés dynamiquement depuis le profil actif —
un secret trouvé dans n'importe quel fichier (y compris ce script lui-même) bloque et
supprime l'archive plutôt que de la laisser partir.

Usage:
  python scripts/make_kit.py [--output job-hunt-kit_nom.zip]
"""
import argparse
from datetime import datetime
import fnmatch
import json
import os
import sys
import zipfile

from typing import List, Optional, Set

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

EXCLUDE_PATTERNS: List[str] = [
    # Secrets
    "config/.notion_token",
    "config/credentials.json",
    "config/gmail_token.json",
    "config/auth_url.txt",
    ".env",
    "*.env",

    # Runtime & Local Cache
    "outputs/*",
    "logs/*",
    "state/*",
    "out/*",
    ".v2c/*",
    ".video_agent/*",
    ".zcode/*",
    ".venv/*",
    "__pycache__/*",
    "*/__pycache__/*",
    "*.pyc",
    ".git/*",
    ".claude/settings.local.json",
    ".claude/scheduled_tasks.lock",
    "job-hunt-kit_*.zip",

    # Framework de règles personnel de l'utilisateur (.claude/rules/), pas spécifique à ce
    # projet — référence gstack, un tracker "Propulse V2" et des défauts Next.js/Supabase
    # sans rapport avec ce kit Python. Découvert le 2026-09-08 : partagerait des règles
    # incohérentes/déroutantes avec le projet reçu par un tiers. Seules les règles
    # réellement génériques restent (00-core, audit sécurité, quality-gate, context7-docs,
    # computer-use-files, session-start — ce dernier retiré de cette liste le 2026-09-14 :
    # son contenu réel est spécifique au Job-Hunt Kit, pas au framework personnel, cf.
    # CLAUDE.md § Conventions).
    ".claude/rules/00-dispatcher-skills.mdc",
    ".claude/rules/01-skill-router.mdc",
    ".claude/rules/20-ecriture-multiagents.mdc",
    ".claude/rules/20-new-project.mdc",
    ".claude/rules/30-new-feature.mdc",

    # Personal PDFs in root if any
    "CV_*.pdf",
    "Lettre_*.pdf",

    # Données/session personnelles (audit daté, routine liée au compte de l'utilisateur,
    # page de référence visuelle statique non paramétrée) — cf. décision du 2026-09-08 :
    # ce ne sont pas des secrets d'accès, mais des artefacts propres à CE déploiement,
    # jamais génériques comme le reste de la doc.
    "index.html",
    "docs/plans/2026-09-07-*.md",
    "config/apply-routine-schedule-prompt.md",
]

SECRET_KEYWORDS: List[str] = [
    ".notion_token",
    "credentials.json",
    "gmail_token.json",
    "settings.local.json"
]

# Extensions de fichiers texte dont le contenu est scanné par l'audit ci-dessous (les
# binaires — .pdf, .zip, .png — ne sont pas lisibles comme du texte et n'ont pas à l'être :
# les PDF personnels sont déjà exclus par pattern, jamais générés dans un dossier partagé).
TEXT_EXTENSIONS: Set[str] = {
    ".py", ".json", ".md", ".yaml", ".yml", ".css", ".html", ".txt", ".sh", ".bat", ".mdc",
}


def is_excluded(rel_path: str) -> bool:
    rel_normalized = rel_path.replace("\\", "/")
    for pat in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_normalized, pat) or fnmatch.fnmatch(os.path.basename(rel_normalized), pat):
            # Exception : garder les .gitkeep
            if rel_normalized.endswith(".gitkeep"):
                return False
            return True
    return False


def build_kit_zip(output_path: Optional[str] = None) -> str:
    today_str = datetime.now().strftime("%Y%m%d")
    out_zip: str = output_path or os.path.join(ROOT, f"job-hunt-kit_{today_str}.zip")

    print(f"📦 Création du Job-Hunt Kit : {os.path.basename(out_zip)}...")
    included_files: List[str] = []

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(ROOT):
            # Filtre des dossiers
            dirs[:] = [d for d in dirs if not is_excluded(os.path.relpath(os.path.join(root, d), ROOT))]

            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, ROOT)

                if is_excluded(rel_path):
                    continue

                # Remplacement des fichiers contenant des données personnelles par les templates
                rel_norm = rel_path.replace("\\", "/")
                
                # config/notion.json -> remplacer par config/notion.template.json
                if rel_norm == "config/notion.json":
                    template_notion = os.path.join(ROOT, "config", "notion.template.json")
                    if os.path.isfile(template_notion):
                        zipf.write(template_notion, arcname="config/notion.json")
                        included_files.append("config/notion.json (depuis notion.template.json)")
                    continue

                # templates/cv/cv-data.json -> remplacer par templates/cv/cv-data.template.json
                if rel_norm == "templates/cv/cv-data.json":
                    template_cv = os.path.join(ROOT, "templates", "cv", "cv-data.template.json")
                    if os.path.isfile(template_cv):
                        zipf.write(template_cv, arcname="templates/cv/cv-data.json")
                        included_files.append("templates/cv/cv-data.json (depuis cv-data.template.json)")
                    continue

                # templates/cv/cv-data.en.json -> remplacer par templates/cv/cv-data.en.template.json
                if rel_norm == "templates/cv/cv-data.en.json":
                    template_cv_en = os.path.join(ROOT, "templates", "cv", "cv-data.en.template.json")
                    if os.path.isfile(template_cv_en):
                        zipf.write(template_cv_en, arcname="templates/cv/cv-data.en.json")
                        included_files.append("templates/cv/cv-data.en.json (depuis cv-data.en.template.json)")
                    continue

                zipf.write(abs_path, arcname=rel_path)
                included_files.append(rel_path)

        # S'assurer que les dossiers vides essentiels ont leur .gitkeep dans le zip
        for folder in ["state", "outputs", "logs"]:
            keep_rel = f"{folder}/.gitkeep"
            if keep_rel not in zipf.namelist():
                zipf.writestr(keep_rel, "")
                included_files.append(keep_rel)

    # Vérification de sécurité du contenu de l'archive.
    # Les valeurs recherchées sont chargées dynamiquement depuis le profil réel (jamais
    # codées en dur ici : un script qui grave l'email/téléphone du candidat en clair dans
    # sa propre source les diffuserait lui-même à chaque partage du kit — cf. correctif du
    # 2026-09-08, la version précédente de ce script avait exactement ce défaut).
    print("\n🔍 Audit de sécurité de l'archive créée...")
    audit_errors: List[str] = []

    pii_values: List[str] = []
    try:
        from profile import load_personal
        personal = load_personal()
        for key in ("email", "telephone"):
            val = (personal.get(key) or "").strip()
            if val:
                pii_values.append(val)
    except Exception as e:
        print(f"[note] Profil illisible, audit du contenu texte limité aux secrets connus : {e}", file=sys.stderr)

    with zipfile.ZipFile(out_zip, "r") as zipf:
        names = zipf.namelist()
        for name in names:
            for kw in SECRET_KEYWORDS:
                if kw in name:
                    audit_errors.append(f"ALERTE : Secret détecté dans l'archive -> {name}")

            if pii_values and os.path.splitext(name)[1].lower() in TEXT_EXTENSIONS:
                try:
                    content = zipf.read(name).decode("utf-8")
                except (UnicodeDecodeError, KeyError):
                    continue
                for val in pii_values:
                    if val in content:
                        audit_errors.append(f"ALERTE : Donnée personnelle résiduelle ({val}) dans {name}")

    if audit_errors:
        os.remove(out_zip)
        print("\n❌ ÉCHEC DE L'AUDIT DE SÉCURITÉ :")
        for err in audit_errors:
            print(f"  - {err}")
        sys.exit(1)

    size_kb = os.path.getsize(out_zip) / 1024
    print(f"✅ Audit validé : aucun secret ni donnée privée.")
    print(f"📁 Archive prête : {out_zip} ({len(included_files)} fichiers, {size_kb:.1f} KB)\n")
    return out_zip


def main() -> None:
    parser = argparse.ArgumentParser(description="Générer le zip de partage du Job-Hunt Kit")
    parser.add_argument("--output", help="Nom du fichier zip de sortie")
    args = parser.parse_args()

    build_kit_zip(args.output)


if __name__ == "__main__":
    main()
