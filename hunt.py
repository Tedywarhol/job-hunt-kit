#!/usr/bin/env python3
"""CLI Unifiee et Navigation Interactive du Job-Hunt Kit.

Point d'entree unique pour piloter le cycle de recherche :
initialisation, veille automatique, personnalisation de CV/lettres, dashboard et tests.

Usage:
  python hunt.py                 # Menu interactif
  python hunt.py apply [slug]    # Generation directe ou guidee
  python hunt.py open [slug]     # Ouvrir le dossier / PDF
  python hunt.py status          # Diagnostic
  python hunt.py stats           # Tableau de bord
"""
import argparse
from datetime import datetime
import glob
import json
import os
import platform
import re
import subprocess
import sys
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT: str = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from profile import date_lettre_aujourdhui, doc_base_names, load_personal, ville_from_localisation
from render_cv import find_chrome
from logutil import log_error

PY: str = sys.executable


# -----------------------------------------------------------------------------
# Helpers d'Affichage & Navigation
# -----------------------------------------------------------------------------

def clear_screen() -> None:
    """Nettoie l'ecran du terminal pour une transition propre si interactif."""
    if sys.stdout.isatty():
        os.system("cls" if platform.system() == "Windows" else "clear")


def pause() -> None:
    """Pause interactive avant de revenir au menu."""
    if sys.stdin.isatty():
        try:
            print()
            input("  Appuyez sur [Entree] pour continuer...")
        except (EOFError, KeyboardInterrupt):
            pass


def render_banner(subtitle: str = "") -> None:
    """Affiche un en-tete sobre et clair."""
    p = load_personal()
    nom = p.get("nom", "Candidat").upper()
    now_str = datetime.now().strftime("%H:%M")
    
    print("=" * 66)
    print(f"  JOB-HUNT KIT  |  Candidat : {nom:<22} |  Heure : {now_str}")
    if subtitle:
        print(f"  Section : {subtitle}")
    print("=" * 66)
    print()


def open_file(file_path: str) -> None:
    """Ouvre un fichier dans le visualiseur par defaut du systeme."""
    if not os.path.exists(file_path):
        return
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", file_path], check=False)
        else:
            subprocess.run(["xdg-open", file_path], check=False)
    except Exception as e:
        log_error(f"open_file({file_path})", e)


def open_directory(dir_path: str) -> None:
    """Ouvre un repertoire dans l'explorateur de fichiers du systeme."""
    if not os.path.isdir(dir_path):
        return
    try:
        if platform.system() == "Windows":
            os.startfile(dir_path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", dir_path], check=False)
        else:
            subprocess.run(["xdg-open", dir_path], check=False)
    except Exception as e:
        log_error(f"open_directory({dir_path})", e)


def slugify(text: str) -> str:
    """Convertit une chaine en slug URL propre."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)


def run_script(script_name: str, args_list: List[str]) -> int:
    script_path = os.path.join(ROOT, "scripts", script_name)
    cmd = [PY, script_path] + args_list
    res = subprocess.run(cmd)
    return res.returncode


def load_available_opportunities() -> List[Dict[str, Any]]:
    """Charge toutes les opportunites detectees et les trie par pertinence et recence."""
    offers: List[Dict[str, Any]] = []
    seen = set()

    for fname in ["pass_alternance_scored.json", "pending-notion-upsert.json"]:
        path = os.path.join(ROOT, "state", fname)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    items = raw.get("offres", []) if isinstance(raw, dict) else raw
                    for item in items:
                        lien = item.get("lien")
                        if lien and lien not in seen:
                            seen.add(lien)
                            offers.append(item)
            except Exception as e:
                log_error(f"load_available_opportunities({fname})", e)

    offers.sort(key=lambda x: (int(x.get("score") or 0), str(x.get("date_publication") or "")), reverse=True)
    return offers


def create_application_scaffolding(
    slug: str, entreprise: str, poste: str, profile_type: str,
    mots_cles: Optional[List[str]] = None, lien: Optional[str] = None,
) -> str:
    """Initialise un dossier de candidature avec variables pre-remplies."""
    target_dir = os.path.join(ROOT, "outputs", slug)
    os.makedirs(target_dir, exist_ok=True)

    personal = load_personal()
    ville = ville_from_localisation(personal)
    date_str = date_lettre_aujourdhui()

    keywords = mots_cles or [entreprise, poste, "Python", "IA", "SQL", "Machine Learning"]

    cv_vars_path = os.path.join(target_dir, "cv-vars.json")
    if not os.path.isfile(cv_vars_path):
        cv_vars = {
            "titre": f"{poste} ({'Alternance 24 mois' if profile_type == 'alternance' else 'Stage 6 mois'})",
            "badge_titre": "Data & IA",
            "accroche": f"Candidat motive pour rejoindre {entreprise} sur le poste de {poste}. Double competence en modelisation, IA generative et ingenierie de donnees.",
            "competences_ordre": ["ia", "python", "sql", "cloud"],
            "mots_cles_ats": keywords,
        }
        with open(cv_vars_path, "w", encoding="utf-8") as f:
            json.dump(cv_vars, f, ensure_ascii=False, indent=2)

    lettre_vars_path = os.path.join(target_dir, "lettre-vars.json")
    if not os.path.isfile(lettre_vars_path):
        lettre_vars = {
            "type": profile_type,
            "entreprise": entreprise,
            "poste": poste,
            # Lien de l'offre d'origine, quand connu : permet à check_consistency.py de
            # retrouver la page Notion sans deviner sur un match texte entreprise/poste,
            # dont la formulation diverge souvent entre les deux (cf. audit 2026-09-07, M3).
            "lien": lien or "",
            "destinataire": "Madame, Monsieur",
            "date": date_str,
            "ville_candidat": ville,
            "objet": f"Candidature — {poste} ({'Alternance 24 mois' if profile_type == 'alternance' else 'Stage 6 mois'})",
            "paragraphes": [
                f"Votre opportunite de « {poste} » au sein de {entreprise} a particulierement retenu mon attention.",
                "Actuellement en cycle d'ingenieur specialise en Data Science et Intelligence Artificielle a Paris, je souhaite mettre ma rigueur methodologique, ma curiosite et mes competences techniques au service de vos projets.",
                [
                    "Conception et deploiement de pipelines de donnees fiables et monitores.",
                    "Developpement de modeles predictifs et d'architectures d'IA generative orientes impact metier.",
                    "Restitution claire via des tableaux de bord interactifs et collaboration transverse.",
                ],
                f"Integrer {entreprise} represente pour moi l'opportunite ideale de contribuer activement a vos defis technologiques.",
            ],
        }
        with open(lettre_vars_path, "w", encoding="utf-8") as f:
            json.dump(lettre_vars, f, ensure_ascii=False, indent=2)

    return target_dir


# -----------------------------------------------------------------------------
# Commandes Core
# -----------------------------------------------------------------------------

def cmd_init(args: Optional[argparse.Namespace] = None) -> int:
    forward_args: List[str] = []
    if args:
        if getattr(args, "fichier", None):
            forward_args += ["--fichier", args.fichier]
        if getattr(args, "theme", None):
            forward_args += ["--theme", args.theme]
        if getattr(args, "notion_token", None):
            forward_args += ["--notion-token", args.notion_token]
        if getattr(args, "notion_page_url", None):
            forward_args += ["--notion-page-url", args.notion_page_url]
        if getattr(args, "skip_deps", False):
            forward_args.append("--skip-deps")
        if getattr(args, "skip_gmail", False):
            forward_args.append("--skip-gmail")
        if getattr(args, "skip_notion", False):
            forward_args.append("--skip-notion")
        if getattr(args, "force", False):
            forward_args.append("--force")
        if getattr(args, "non_interactive", False):
            forward_args.append("--non-interactive")
    return run_script("init.py", forward_args)


def cmd_apply(args: Optional[argparse.Namespace] = None) -> int:
    slug = getattr(args, "slug", None) if args else None
    profile = getattr(args, "profile", None) if args else None

    # Mode interactif guide si aucun slug n'est fourni
    if not slug:
        clear_screen()
        render_banner("Creer une nouvelle candidature sur-mesure")
        available_offers = load_available_opportunities()

        try:
            if available_offers:
                print("  Source de l'opportunite :")
                print("    1. Choisir parmi les meilleures offres detectees (Recommande)")
                print("    2. Saisir manuellement une nouvelle entreprise")
                print()
                src_choice = input("  Votre choix [1/2] (defaut: 1) : ").strip()

                if src_choice != "2":
                    print("\n  Top 10 des opportunites recentes :")
                    for i, o in enumerate(available_offers[:10], 1):
                        score = o.get("score", 70)
                        ent = str(o.get("entreprise") or o.get("administration") or "Entreprise")[:20]
                        titre = str(o.get("poste") or o.get("titre") or "Poste")[:38]
                        print(f"    [{i:>2}] Score: {score}/100 | {ent:<20} | {titre}")

                    sel_idx_str = input("\n  Selectionnez une offre [1-10] : ").strip()
                    try:
                        idx = int(sel_idx_str) - 1
                        if 0 <= idx < min(10, len(available_offers)):
                            selected = available_offers[idx]
                            entreprise = str(selected.get("entreprise") or selected.get("administration") or "Entreprise")
                            poste = str(selected.get("poste") or selected.get("titre") or "Data Scientist")
                            profile_type = selected.get("type", "alternance")
                            slug = slugify(f"{entreprise}-{poste}-{profile_type}")
                            create_application_scaffolding(slug, entreprise, poste, profile_type, lien=selected.get("lien"))
                            profile = profile_type
                    except ValueError:
                        print("  Selection invalide. Passage en saisie manuelle.")

            if not slug:
                entreprise = input("  Nom de l'entreprise cible (ex: Doctolib) : ").strip()
                if not entreprise:
                    print("  Annule : nom d'entreprise requis.")
                    return 1
                poste = input("  Intitule du poste vise (ex: Data Scientist Alternance) : ").strip() or "Data Scientist & IA"
                print("\n  Type de contrat :")
                print("    1. Alternance (24 mois)")
                print("    2. Stage (6 mois)")
                c_choice = input("  Votre choix [1/2] (defaut: 1) : ").strip()
                profile_type = "stage" if c_choice == "2" else "alternance"

                slug = slugify(f"{entreprise}-{poste}-{profile_type}")
                create_application_scaffolding(slug, entreprise, poste, profile_type)
                profile = profile_type

        except (EOFError, KeyboardInterrupt):
            return 1

    folder = os.path.join(ROOT, "outputs", slug)
    lettre_vars_path = os.path.join(folder, "lettre-vars.json")
    if not profile and os.path.isfile(lettre_vars_path):
        try:
            with open(lettre_vars_path, "r", encoding="utf-8") as f:
                lv = json.load(f)
            if lv.get("type") in ["stage", "alternance"]:
                profile = lv["type"]
        except Exception as e:
            log_error(f"cmd_apply: lecture {lettre_vars_path}", e)

    profile = profile or "alternance"
    print(f"\n  Compilation du CV et de la Lettre PDF pour : outputs/{slug}/")
    rc = run_script("build_application.py", ["--slug", slug, "--profile", profile])

    # Proposer d'ouvrir les PDF generes
    if rc == 0:
        personal = load_personal()
        cv_base, lettre_base = doc_base_names(personal)
        cv_pdf = os.path.join(folder, f"{cv_base}.pdf")
        lettre_pdf = os.path.join(folder, f"{lettre_base}.pdf")

        if os.path.isfile(cv_pdf):
            try:
                open_resp = input("\n  Ouvrir les PDF generes dans votre lecteur ? [O/n] : ").strip().lower()
                if open_resp not in ["n", "non"]:
                    open_file(cv_pdf)
                    if os.path.isfile(lettre_pdf):
                        open_file(lettre_pdf)
            except (EOFError, KeyboardInterrupt):
                pass
    return rc


def cmd_open(args: argparse.Namespace) -> int:
    """Ouvre le dossier de candidature ou ses fichiers PDF."""
    slug = args.slug
    folder = os.path.join(ROOT, "outputs", slug)
    if not os.path.isdir(folder):
        print(f"Dossier introuvable : outputs/{slug}")
        return 1

    personal = load_personal()
    cv_base, lettre_base = doc_base_names(personal)
    cv_pdf = os.path.join(folder, f"{cv_base}.pdf")
    lettre_pdf = os.path.join(folder, f"{lettre_base}.pdf")

    if os.path.isfile(cv_pdf):
        open_file(cv_pdf)
    if os.path.isfile(lettre_pdf):
        open_file(lettre_pdf)
    open_directory(folder)
    return 0


def cmd_cv(args: Optional[argparse.Namespace] = None) -> int:
    profile: str = getattr(args, "profile", "alternance") or "alternance"
    forward_args: List[str] = ["--profile", profile]
    if args and getattr(args, "vars", None):
        forward_args += ["--vars", args.vars]
    if args and getattr(args, "out", None):
        forward_args += ["--out", args.out]
    if not args or getattr(args, "pdf", False) or not getattr(args, "out", None):
        forward_args.append("--pdf")

    rc = run_script("render_cv.py", forward_args)
    if rc == 0:
        personal = load_personal()
        cv_base, _ = doc_base_names(personal)
        suffix = f"_{profile.capitalize()}" if profile != "alternance" else "_Alternance"
        out_pdf = os.path.join(ROOT, "outputs", f"{cv_base}{suffix}.pdf")
        if not os.path.isfile(out_pdf):
            out_pdf = os.path.join(ROOT, "outputs", f"{cv_base}.pdf")
        if os.path.isfile(out_pdf):
            try:
                open_resp = input("\n  Ouvrir le CV PDF dans votre lecteur ? [O/n] : ").strip().lower()
                if open_resp not in ["n", "non"]:
                    open_file(out_pdf)
            except (EOFError, KeyboardInterrupt):
                pass
    return rc


def cmd_lettre(args: argparse.Namespace) -> int:
    vars_file: str = args.vars
    if not os.path.isfile(vars_file):
        possible = os.path.join(ROOT, "outputs", args.vars, "lettre-vars.json")
        if os.path.isfile(possible):
            vars_file = possible
        else:
            sys.exit(f"Fichier de variables introuvable : {args.vars}")
    forward_args: List[str] = ["--vars", vars_file]
    if args.out:
        forward_args += ["--out", args.out]
    if args.pdf or not args.out:
        forward_args.append("--pdf")
    return run_script("render_lettre.py", forward_args)


def cmd_scan(args: Optional[argparse.Namespace] = None) -> int:
    scan_ats = getattr(args, "ats", False) if args else True
    scan_pass = getattr(args, "pass_source", False) if args else True
    if args and getattr(args, "all", False):
        scan_ats = True
        scan_pass = True

    if scan_ats:
        print("\nInterrogation des API publiques ATS (Greenhouse, Lever, Ashby)...")
        rc_ats = run_script("scrape_ats_api.py", [])
        if rc_ats != 0 and not scan_pass:
            return rc_ats

    if scan_pass:
        print("\nDemarrage de la veille PASS (Fonction Publique)...")
        rc = run_script("scrape_pass.py", [])
        if rc != 0:
            return rc
        print("\nEnrichissement des offres...")
        rc = run_script("enrich_pass_offers.py", [])
        if rc != 0:
            return rc
        print("\nFiltrage et notation des opportunites...")
        return run_script("filter_alternance_pass.py", [])

    return 0


def cmd_notion(args: argparse.Namespace) -> int:
    sub = args.notion_sub
    if sub == "list":
        return run_script("notion_apply.py", ["list"])
    elif sub == "mark":
        forward = ["mark", "--url", args.url]
        if args.statut:
            forward += ["--statut", args.statut]
        if args.date:
            forward += ["--date", args.date]
        if args.notes:
            forward += ["--notes", args.notes]
        return run_script("notion_apply.py", forward)
    elif sub == "push":
        return run_script("push_pass_to_notion.py", [])
    else:
        print("Sous-commande Notion manquante : list | mark | push")
        return 1


def cmd_draft(args: Optional[argparse.Namespace] = None) -> int:
    if args and getattr(args, "to", None) and getattr(args, "subject", None):
        forward = ["--to", args.to, "--subject", args.subject]
        if getattr(args, "body", None):
            forward += ["--body", args.body]
        if getattr(args, "body_file", None):
            forward += ["--body-file", args.body_file]
        if getattr(args, "cv", None):
            forward += ["--cv", args.cv]
        return run_script("create_gmail_draft.py", forward)
    else:
        top_count = str(getattr(args, "top", 5) if args else 5)
        return run_script("generate_alternance_drafts.py", ["--top", top_count])


def cmd_profile(args: argparse.Namespace) -> int:
    if args.profile_sub == "import":
        return cmd_profile_import(args)
    print("Sous-commande profile manquante : import")
    return 1


def cmd_profile_import(args: argparse.Namespace) -> int:
    """Extrait le texte d'un CV/document et le sauvegarde pour une reprise guidee.

    N'interprete rien lui-meme (regex/heuristique sur un CV en format libre serait
    peu fiable) : la fusion dans templates/cv/cv-data.json se fait avec Claude Code via
    le skill `import-profile`, qui lit le texte extrait, compare a l'etat actuel, et ne
    modifie rien sans confirmation explicite.
    """
    source = args.path
    if not os.path.isfile(source):
        print(f"Fichier introuvable : {source}")
        return 1

    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    out_path = os.path.join(ROOT, "state", "import-source.txt")
    rc = run_script("extract_document_text.py", [source, "--out", out_path])
    if rc != 0:
        return rc

    print(f"\nTexte extrait dans : {out_path}")
    print("\nPour la fusion dans templates/cv/cv-data.json (jamais automatique, toujours avec confirmation) :")
    print(f'  Dans Claude Code : /import-profile "{source}"')
    print("  (le skill relit le texte extrait, compare a ton profil actuel, et te presente le diff avant d'ecrire quoi que ce soit.)")
    return 0


def cmd_kit(args: Optional[argparse.Namespace] = None) -> int:
    forward: List[str] = []
    if args and getattr(args, "output", None):
        forward += ["--output", args.output]
    return run_script("make_kit.py", forward)


def cmd_test(args: Optional[argparse.Namespace] = None) -> int:
    test_args: List[str] = [PY, "-m", "pytest", "tests/"]
    if args and getattr(args, "verbose", False):
        test_args.append("-v")
    if args and getattr(args, "k", None):
        test_args += ["-k", args.k]
    res = subprocess.run(test_args)
    return res.returncode


def cmd_status(args: Optional[argparse.Namespace] = None) -> int:
    p = load_personal()
    chrome_path = find_chrome()
    notion_token_file = os.path.join(ROOT, "config", ".notion_token")
    notion_configured = os.path.isfile(notion_token_file) or bool(os.environ.get("NOTION_TOKEN"))
    gmail_token_file = os.path.join(ROOT, "config", "gmail_token.json")
    gmail_configured = os.path.isfile(gmail_token_file)

    output_dirs = [d for d in glob.glob(os.path.join(ROOT, "outputs", "*")) if os.path.isdir(d)]
    
    pass_scored = os.path.join(ROOT, "state", "pass_alternance_scored.json")
    pass_count = 0
    if os.path.isfile(pass_scored):
        try:
            with open(pass_scored, "r", encoding="utf-8") as f:
                pass_count = len(json.load(f))
        except Exception as e:
            log_error(f"cmd_status: lecture {pass_scored}", e)

    print("\n" + "=" * 60)
    print("JOB-HUNT KIT — DIAGNOSTIC DU WORKSPACE")
    print("=" * 60)
    print(f"  Candidat actif    : {p.get('nom', 'Non configure')}")
    print(f"  Email principal   : {p.get('email', 'Non configure')}")
    print(f"  Localisation      : {p.get('localisation', 'Non configure')}")
    print(f"  Moteur PDF        : {'OK (' + chrome_path + ')' if chrome_path else 'Chrome/Edge introuvable'}")
    print(f"  Base Notion       : {'Connectee' if notion_configured else 'Non configuree'}")
    print(f"  OAuth Gmail       : {'Autorise' if gmail_configured else 'Non configure'}")
    print(f"  Dossiers d'offres : {len(output_dirs)} candidature(s) preparee(s)")
    print(f"  Offres PASS dispo : {pass_count} opportunite(s) scoree(s)")
    print("=" * 60 + "\n")
    return 0


def cmd_stats(args: Optional[argparse.Namespace] = None) -> int:
    return run_script("dashboard.py", [])


# -----------------------------------------------------------------------------
# Sous-Menus Interactifs Sobres
# -----------------------------------------------------------------------------

def menu_scan() -> None:
    """Sous-menu dedie a la veille d'offres."""
    while True:
        clear_screen()
        render_banner("Veille & Radar d'opportunites")
        print("  1. Scanner les API ATS (Greenhouse, Lever, Ashby)")
        print("  2. Scanner la plateforme PASS (Fonction Publique)")
        print("  3. Veille complete (Toutes sources confondues)")
        print("  0. Retour")
        print()
        try:
            c = input("  Choix [0-3] : ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if c == "1":
            run_script("scrape_ats_api.py", [])
            pause()
        elif c == "2":
            run_script("scrape_pass.py", [])
            run_script("enrich_pass_offers.py", [])
            run_script("filter_alternance_pass.py", [])
            pause()
        elif c == "3":
            cmd_scan()
            pause()
        elif c in ["0", "b", "r", "q"]:
            break


def menu_notion() -> None:
    """Sous-menu dedie a la gestion Notion."""
    while True:
        clear_screen()
        render_banner("Synchronisation Notion")
        print("  1. Lister les opportunites a traiter")
        print("  2. Pousser les offres recentes vers Notion")
        print("  3. Marquer une offre comme postulee")
        print("  0. Retour")
        print()
        try:
            c = input("  Choix [0-3] : ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if c == "1":
            run_script("notion_apply.py", ["list"])
            pause()
        elif c == "2":
            run_script("push_pass_to_notion.py", [])
            pause()
        elif c == "3":
            url = input("  URL de l'offre a marquer : ").strip()
            if url:
                run_script("notion_apply.py", ["mark", "--url", url, "--statut", "Postule"])
            pause()
        elif c in ["0", "b", "r", "q"]:
            break


def menu_cv_preview() -> None:
    """Sous-menu dedie a la previsualisation des CVs."""
    while True:
        clear_screen()
        render_banner("Previsualisation du CV Master")
        print("  1. Compiler le CV Alternance (24 mois)")
        print("  2. Compiler le CV Stage (6 mois)")
        print("  0. Retour")
        print()
        try:
            c = input("  Choix [0-2] : ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if c == "1":
            cmd_cv(argparse.Namespace(profile="alternance", vars=None, out=None, pdf=True))
            pause()
        elif c == "2":
            cmd_cv(argparse.Namespace(profile="stage", vars=None, out=None, pdf=True))
            pause()
        elif c in ["0", "b", "r", "q"]:
            break


def menu_manage_applications() -> None:
    """Sous-menu de gestion des candidatures existantes."""
    while True:
        clear_screen()
        render_banner("Gestion des candidatures preparees (outputs/)")
        output_dirs = sorted([d for d in glob.glob(os.path.join(ROOT, "outputs", "*")) if os.path.isdir(d)])
        if not output_dirs:
            print("  Aucun dossier de candidature cree pour le moment.")
            pause()
            break

        print("  Dossiers de candidature disponibles :")
        for i, d in enumerate(output_dirs, 1):
            slug = os.path.basename(d)
            cv_exists = "CV OK" if any(f.endswith(".pdf") and "CV" in f for f in os.listdir(d)) else "Sans CV PDF"
            print(f"    [{i:>2}] {slug:<45} ({cv_exists})")

        print("\n  0. Retour")
        print()
        try:
            c = input("  Selectionnez un dossier [1-N] ou 0 : ").strip()
            if c in ["0", "b", "r", "q"] or not c:
                break
            idx = int(c) - 1
            if 0 <= idx < len(output_dirs):
                sel_dir = output_dirs[idx]
                slug = os.path.basename(sel_dir)
                print(f"\n  Actions pour {slug} :")
                print("    1. Recompiler CV & Lettre PDF")
                print("    2. Ouvrir le dossier dans l'explorateur")
                print("    3. Ouvrir les fichiers PDF")
                act = input("  Votre choix [1-3] : ").strip()
                if act == "1":
                    cmd_apply(argparse.Namespace(slug=slug, profile=None))
                elif act == "2":
                    open_directory(sel_dir)
                elif act == "3":
                    personal = load_personal()
                    cv_base, lettre_base = doc_base_names(personal)
                    cv_pdf = os.path.join(sel_dir, f"{cv_base}.pdf")
                    lettre_pdf = os.path.join(sel_dir, f"{lettre_base}.pdf")
                    if os.path.isfile(cv_pdf):
                        open_file(cv_pdf)
                    if os.path.isfile(lettre_pdf):
                        open_file(lettre_pdf)
                pause()
        except (ValueError, EOFError, KeyboardInterrupt):
            break


def interactive_menu() -> None:
    """Menu interactif principal epure, sobre et fluide."""
    while True:
        clear_screen()
        render_banner("Menu Principal")
        print("  1. Generer une candidature sur-mesure (CV + Lettre PDF)")
        print("  2. Lancer la veille d'offres (ATS & PASS)")
        print("  3. Tableau de bord & Suivi des candidatures")
        print("  4. Consulter & Ouvrir mes candidatures existantes")
        print("  5. Preparer mes brouillons d'emails Gmail")
        print("  6. Previsualiser mon CV PDF (Alternance / Stage)")
        print("  7. Synchroniser avec Notion")
        print("  8. Modifier mon profil ou theme graphique")
        print("  9. Verifier l'installation & Lancer les tests")
        print("  0. Quitter")
        print()

        try:
            choice = input("  Choix [0-9] : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Fermeture du kit.\n")
            break

        if choice == "1":
            cmd_apply()
            pause()
        elif choice == "2":
            menu_scan()
        elif choice == "3":
            clear_screen()
            cmd_stats()
            pause()
        elif choice == "4":
            menu_manage_applications()
        elif choice == "5":
            clear_screen()
            cmd_draft()
            pause()
        elif choice == "6":
            menu_cv_preview()
        elif choice == "7":
            menu_notion()
        elif choice == "8":
            cmd_init()
            pause()
        elif choice == "9":
            clear_screen()
            cmd_test()
            pause()
        elif choice in ["0", "q", "quit", "exit"]:
            print("\n  Fermeture du kit.\n")
            break


def main() -> None:
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        prog="hunt",
        description="CLI Unifiee du Job-Hunt Kit : veille, personnalisation de CV/lettres et gestion de candidatures."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Commandes disponibles")

    # menu
    subparsers.add_parser("menu", help="Ouvrir le menu interactif")

    # init
    p_init = subparsers.add_parser("init", aliases=["setup"], help="Initialiser le workspace et le profil")
    p_init.add_argument("--fichier", "--profile", help="Fichier JSON de profil pre-rempli")
    p_init.add_argument("--theme", help="Theme (navy, emerald, bordeaux, #HEX)")
    p_init.add_argument("--notion-token", help="Token Notion Integration")
    p_init.add_argument("--notion-page-url", help="URL de page parente Notion")
    p_init.add_argument("--skip-deps", action="store_true", help="Passer l'installation pip")
    p_init.add_argument("--skip-gmail", action="store_true", help="Passer OAuth Gmail")
    p_init.add_argument("--skip-notion", action="store_true", help="Passer la configuration Notion")
    p_init.add_argument("--force", action="store_true", help="Ecraser les profils existants sans confirmation")
    p_init.add_argument("--non-interactive", action="store_true", help="Mode batch non-interactif")

    # apply
    p_apply = subparsers.add_parser("apply", aliases=["build"], help="Generer CV + Lettre PDF pour une offre")
    p_apply.add_argument("slug", nargs="?", default=None, help="Nom du dossier sous outputs/ (optionnel pour mode guide)")
    p_apply.add_argument("--profile", choices=["alternance", "stage"], default=None, help="Type de profil")

    # open
    p_open = subparsers.add_parser("open", help="Ouvrir le dossier et les PDF d'une candidature")
    p_open.add_argument("slug", help="Nom du dossier sous outputs/")

    # cv
    p_cv = subparsers.add_parser("cv", aliases=["render-cv"], help="Generer un CV de previsualisation")
    p_cv.add_argument("--profile", choices=["alternance", "stage"], default="alternance")
    p_cv.add_argument("--vars", help="Chemin vers cv-vars.json optionnel")
    p_cv.add_argument("--out", help="Chemin du fichier HTML de sortie")
    p_cv.add_argument("--pdf", action="store_true", help="Generer le PDF")

    # lettre
    p_lettre = subparsers.add_parser("lettre", aliases=["render-lettre"], help="Generer une lettre de motivation")
    p_lettre.add_argument("vars", help="Chemin vers lettre-vars.json ou slug sous outputs/")
    p_lettre.add_argument("--out", help="Fichier de sortie")
    p_lettre.add_argument("--pdf", action="store_true", help="Generer le PDF")

    # scan
    p_scan = subparsers.add_parser("scan", aliases=["scrape"], help="Lancer la veille d'offres (PASS & ATS)")
    p_scan.add_argument("--ats", action="store_true", help="Scraper uniquement les API d'ATS (Greenhouse, Lever, Ashby)")
    p_scan.add_argument("--pass", dest="pass_source", action="store_true", help="Scraper uniquement la plateforme PASS")
    p_scan.add_argument("--all", action="store_true", help="Scraper toutes les sources")

    # notion
    p_notion = subparsers.add_parser("notion", aliases=["db"], help="Gerer la base Notion")
    p_notion_subs = p_notion.add_subparsers(dest="notion_sub", required=True)
    p_notion_subs.add_parser("list", help="Lister les offres a traiter")
    p_notion_subs.add_parser("push", help="Pousser les offres vers Notion")
    p_notion_mark = p_notion_subs.add_parser("mark", help="Mettre a jour le statut d'une offre")
    p_notion_mark.add_argument("--url", required=True, help="URL de l'offre")
    p_notion_mark.add_argument("--statut", default="Postule", help="Nouveau statut")
    p_notion_mark.add_argument("--date", help="Date de candidature YYYY-MM-DD")
    p_notion_mark.add_argument("--notes", help="Notes matching")

    # draft
    p_draft = subparsers.add_parser("draft", aliases=["gmail"], help="Creer des brouillons Gmail")
    p_draft.add_argument("--top", type=int, default=5, help="Nombre de meilleures offres PASS a preparer")
    p_draft.add_argument("--to", help="Destinataire pour envoi direct")
    p_draft.add_argument("--subject", help="Objet de l'email")
    p_draft.add_argument("--body", help="Corps du message")
    p_draft.add_argument("--body-file", help="Fichier contenant le corps du message")
    p_draft.add_argument("--cv", help="Chemin du CV PDF joint")

    # profile
    p_profile = subparsers.add_parser("profile", help="Gerer le profil candidat (cv-data.json)")
    p_profile_subs = p_profile.add_subparsers(dest="profile_sub", required=True)
    p_profile_import = p_profile_subs.add_parser(
        "import", help="Extraire le texte d'un CV/document pour mise a jour guidee du profil"
    )
    p_profile_import.add_argument("path", help="Chemin du CV/document (PDF, DOCX, TXT, MD)")

    # kit
    p_kit = subparsers.add_parser("kit", aliases=["pack", "export"], help="Generer l'archive de partage securisee")
    p_kit.add_argument("--output", help="Nom du fichier zip de sortie")

    # test
    p_test = subparsers.add_parser("test", help="Executer la suite de tests automatisee")
    p_test.add_argument("-v", "--verbose", action="store_true", help="Mode verbeux")
    p_test.add_argument("-k", help="Filtrer les tests par nom")

    # status & stats
    subparsers.add_parser("status", aliases=["info"], help="Afficher l'etat technique du workspace")
    subparsers.add_parser("stats", aliases=["dashboard"], help="Afficher le tableau de bord analytique")

    args = parser.parse_args()

    if not args.subcommand:
        interactive_menu()
        return

    dispatch = {
        "menu": lambda a: interactive_menu(),
        "init": cmd_init,
        "setup": cmd_init,
        "apply": cmd_apply,
        "build": cmd_apply,
        "open": cmd_open,
        "cv": cmd_cv,
        "render-cv": cmd_cv,
        "lettre": cmd_lettre,
        "render-lettre": cmd_lettre,
        "scan": cmd_scan,
        "scrape": cmd_scan,
        "notion": cmd_notion,
        "db": cmd_notion,
        "profile": cmd_profile,
        "draft": cmd_draft,
        "gmail": cmd_draft,
        "kit": cmd_kit,
        "pack": cmd_kit,
        "export": cmd_kit,
        "test": cmd_test,
        "status": cmd_status,
        "info": cmd_status,
        "stats": cmd_stats,
        "dashboard": cmd_stats,
    }

    fn = dispatch.get(args.subcommand)
    if fn:
        code = fn(args)
        sys.exit(code or 0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
