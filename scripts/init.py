#!/usr/bin/env python3
"""Script d'initialisation du Job-Hunt Kit.

Configure l'environnement, le profil candidat, le thème graphique,
la base de données Notion et les identifiants en une seule commande.

Usage:
  python scripts/init.py
  python scripts/init.py --fichier profil.json --theme navy --non-interactive
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

from typing import Any, Dict, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


THEMES: Dict[str, Dict[str, str]] = {
    "navy": {"nom": "Navy (par défaut)", "primary": "#323B4C", "primary_dark": "#242B38", "primary_soft": "rgba(50, 59, 76, 0.85)"},
    "emerald": {"nom": "Émeraude", "primary": "#155E4C", "primary_dark": "#0D4235", "primary_soft": "rgba(21, 94, 76, 0.85)"},
    "bordeaux": {"nom": "Bordeaux", "primary": "#7A1F2B", "primary_dark": "#59141E", "primary_soft": "rgba(122, 31, 43, 0.85)"},
}


def check_python_version() -> bool:
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        print(f"[!] Python >= 3.9 requis (version détectée : {v.major}.{v.minor}.{v.micro})")
        return False
    return True


def check_chrome() -> Optional[str]:
    from render_cv import find_chrome
    return find_chrome()


def check_and_install_deps(skip: bool = False) -> bool:
    if skip:
        return True
    req_file = os.path.join(ROOT, "requirements.txt")
    if not os.path.isfile(req_file):
        return True

    print("\n📦 Vérification des dépendances Python...")
    try:
        import bs4  # beautifulsoup4
        import docx  # python-docx (import de profil)
        import googleapiclient  # google-api-python-client
        import pypdf
        # scrapling seul ne suffit pas a verifier l'extra [fetchers] : la lib de base
        # s'importe meme sans curl_cffi/patchright, qui sont requis par scrape_pass.py /
        # enrich_pass_offers.py / scrape_scrapling.py (from scrapling.fetchers import ...).
        from scrapling.fetchers import Fetcher  # noqa: F401
        import yaml  # pyyaml
        print("✅ Toutes les dépendances essentielles sont déjà installées.")
        return True
    except ImportError:
        print("Installation des dépendances manquantes depuis requirements.txt...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])
        if res.returncode != 0:
            return False
        print(
            "ℹ️ Le binaire navigateur pour le scraping stealth n'est pas installé par pip. "
            "Si --stealth échoue plus tard : python -m patchright install chromium"
        )
        return True


def apply_theme(theme_key_or_hex: Optional[str] = None) -> str:
    if not theme_key_or_hex:
        theme_key_or_hex = "navy"

    key = theme_key_or_hex.lower()
    if key in THEMES:
        t = THEMES[key]
        primary = t["primary"]
        primary_dark = t["primary_dark"]
        primary_soft = t["primary_soft"]
    else:
        # Hex personnalisé
        primary = theme_key_or_hex if theme_key_or_hex.startswith("#") else f"#{theme_key_or_hex}"
        primary_dark = primary
        primary_soft = "rgba(50, 59, 76, 0.85)"

    # Mettre à jour cv.css
    cv_css_path = os.path.join(ROOT, "templates", "cv", "cv.css")
    if os.path.isfile(cv_css_path):
        with open(cv_css_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r"--primary:\s*[^;]+;", f"--primary: {primary};", content)
        content = re.sub(r"--primary-dark:\s*[^;]+;", f"--primary-dark: {primary_dark};", content)
        content = re.sub(r"--primary-soft:\s*[^;]+;", f"--primary-soft: {primary_soft};", content)
        with open(cv_css_path, "w", encoding="utf-8") as f:
            f.write(content)

    # Mettre à jour lettre.css
    lettre_css_path = os.path.join(ROOT, "templates", "lettre", "lettre.css")
    if os.path.isfile(lettre_css_path):
        with open(lettre_css_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r"--primary:\s*[^;]+;", f"--primary: {primary};", content)
        content = re.sub(r"--primary-soft:\s*[^;]+;", f"--primary-soft: {primary_soft};", content)
        with open(lettre_css_path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"🎨 Thème appliqué : {primary}")
    return primary


def create_profile_from_file(profile_file_path: str) -> Dict[str, Any]:
    with open(profile_file_path, "r", encoding="utf-8") as f:
        custom_data: Dict[str, Any] = json.load(f)

    template_path = os.path.join(ROOT, "templates", "cv", "cv-data.template.json")
    with open(template_path, "r", encoding="utf-8") as f:
        base_data: Dict[str, Any] = json.load(f)

    # Si le fichier fourni est déjà un cv-data complet
    if "personal" in custom_data and "profiles" in custom_data and "experiences" in custom_data:
        merged = custom_data
    else:
        # Fusion des champs personnels
        merged = base_data.copy()
        if "personal" in custom_data:
            merged["personal"].update(custom_data["personal"])
        elif "nom" in custom_data:
            for k in ["nom", "prenom", "nom_famille", "telephone", "email", "localisation", "linkedin", "linkedin_url", "github_url"]:
                if k in custom_data:
                    merged["personal"][k] = custom_data[k]

        if "badge_titre" in custom_data:
            merged["badge_titre"] = custom_data["badge_titre"]
        if "profil_resume" in custom_data:
            merged["profil_resume"] = custom_data["profil_resume"]
        if "profiles" in custom_data:
            merged["profiles"].update(custom_data["profiles"])
        if "experiences" in custom_data:
            merged["experiences"] = custom_data["experiences"]
        if "projets" in custom_data:
            merged["projets"] = custom_data["projets"]
        if "competences_cles" in custom_data:
            merged["competences_cles"] = custom_data["competences_cles"]
        if "outils" in custom_data:
            merged["outils"] = custom_data["outils"]

    # Suppression du commentaire template
    merged.pop("_lisez_moi", None)

    out_file = os.path.join(ROOT, "templates", "cv", "cv-data.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"✅ Profil importé et sauvegardé dans {out_file}")
    return merged


def prompt_questionnaire() -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("📝 CONFIGURATION DE VOTRE PROFIL CANDIDAT")
    print("=" * 60)

    template_path = os.path.join(ROOT, "templates", "cv", "cv-data.template.json")
    with open(template_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    data.pop("_lisez_moi", None)

    def ask(prompt: str, default: str = "") -> str:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default

    print("\n--- 1. Coordonnées ---")
    prenom = ask("Prénom", "Alexandre")
    nom_fam = ask("Nom de famille (en majuscules)", "DUPONT").upper()
    data["personal"]["prenom"] = prenom
    data["personal"]["nom_famille"] = nom_fam
    data["personal"]["nom"] = f"{prenom} {nom_fam}"
    data["personal"]["email"] = ask("Email", f"{prenom.lower()}.{nom_fam.lower()}@example.com")
    data["personal"]["telephone"] = ask("Téléphone", "+33 6 12 34 56 78")
    data["personal"]["localisation"] = ask("Localisation (Ville (Dpt), Pays)", "Paris (75), France")
    data["personal"]["linkedin"] = f"{prenom} {nom_fam}"
    data["personal"]["linkedin_url"] = ask("URL profil LinkedIn", f"https://www.linkedin.com/in/{prenom.lower()}-{nom_fam.lower()}/")
    data["personal"]["github_url"] = ask("URL GitHub (optionnel)", f"https://github.com/{prenom.lower()}-{nom_fam.lower()}")

    print("\n--- 2. Domaine cible & Positionnement ---")
    data["badge_titre"] = ask("Badge Titre (sidebar)", "Ingénieur Data & IA")
    data["profil_resume"] = ask(
        "Accroche / Résumé de profil",
        "Étudiant en cycle ingénieur Data Science & IA, je conçois et déploie des solutions innovantes "
        "alliant robustesse technique et impact métier concret."
    )

    print("\n--- 3. Type de recherche ---")
    print("  [1] Alternance uniquement")
    print("  [2] Stage uniquement")
    print("  [3] Les deux (Stage ET Alternance)")
    type_choice = ask("Votre choix (1/2/3)", "3")

    if type_choice in ["1", "3"]:
        print("\n--- Formation pour l'Alternance ---")
        alt_ecole = ask("École d'ingénieur / Établissement", "ECE Paris")
        alt_degre = ask("Intitulé de la formation", "Cycle Ingénieur · Data Science & IA")
        alt_lieu = ask("Lieu de formation", "Paris (75)")
        alt_periode = ask("Période", "2026 – 2028")
        alt_spec = ask("Spécialisation / Majeure", "Intelligence Artificielle & Big Data")
        alt_duree = ask("Durée & date de début", "24 mois dès Sep. 2026")
        alt_rythme = ask("Rythme d'alternance", "3 sem. entreprise / 3 sem. école")

        data["profiles"]["alternance"]["titre_defaut"] = f"Alternance {data['badge_titre']}"
        data["profiles"]["alternance"]["target_tags"] = [
            {"icon": "far fa-calendar-alt", "text": alt_duree},
            {"icon": "fas fa-sync-alt", "text": alt_rythme},
            {"icon": "fas fa-map-marker-alt", "text": "Île-de-France / France"}
        ]
        data["profiles"]["alternance"]["disponibilite"] = [
            f"Contrat d'apprentissage · {alt_duree}",
            f"Rythme : {alt_rythme}",
            "Disponible dès septembre 2026"
        ]
        data["profiles"]["alternance"]["formation"] = [
            {
                "periode": alt_periode,
                "intitule": alt_degre,
                "etablissement": alt_ecole,
                "lieu": alt_lieu,
                "detail": f"Spécialisation {alt_spec}"
            }
        ]

    if type_choice in ["2", "3"]:
        print("\n--- Formation pour le Stage ---")
        stg_ecole = ask("École / Établissement", "CESI École d'Ingénieurs")
        stg_degre = ask("Intitulé de la formation", "Cycle Ingénieur · Sciences du Numérique")
        stg_lieu = ask("Lieu", "Nanterre (92)")
        stg_periode = ask("Période", "2025 – 2026")
        stg_spec = ask("Spécialité / Majeure", "Data & Systèmes d'Information")
        stg_duree = ask("Durée du stage", "Stage conventionné · 6 mois")

        data["profiles"]["stage"]["titre_defaut"] = f"Stage {data['badge_titre']}"
        data["profiles"]["stage"]["target_tags"] = [
            {"icon": "far fa-calendar-alt", "text": stg_duree},
            {"icon": "fas fa-clock", "text": "Temps plein"},
            {"icon": "fas fa-map-marker-alt", "text": "Île-de-France / France"}
        ]
        data["profiles"]["stage"]["disponibilite"] = [
            stg_duree,
            "Disponible dès maintenant",
            "Temps plein"
        ]
        data["profiles"]["stage"]["formation"] = [
            {
                "periode": stg_periode,
                "intitule": stg_degre,
                "etablissement": stg_ecole,
                "lieu": stg_lieu,
                "detail": f"Majeure {stg_spec}"
            }
        ]

    out_file = os.path.join(ROOT, "templates", "cv", "cv-data.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ cv-data.json généré avec succès dans {out_file} !")
    return data


def setup_notion_interactive() -> bool:
    print("\n" + "=" * 60)
    print("📊 CONNEXION DE LA BASE NOTION (Optionnel mais recommandé)")
    print("=" * 60)
    ans = input("Voulez-vous configurer la base Notion 'Candidatures' maintenant ? (o/N) : ").strip().lower()
    if ans not in ["o", "oui", "y", "yes"]:
        print("⏩ Configuration Notion ignorée (vous pourrez la faire plus tard avec init_notion_db.py).")
        return False

    token = input("Entrez votre Token Notion Integration (ntn_... ou secret_...) : ").strip()
    page_url = input("Entrez l'URL de votre page Notion parente : ").strip()

    if not token or not page_url:
        print("[!] Token ou URL manquant. Étape passée.")
        return False

    from init_notion_db import create_database, parse_id, save_config, test_token
    parent_id = parse_id(page_url)
    ok, bot_name = test_token(token)
    if not ok:
        print(f"[!] Échec de connexion à Notion : {bot_name}")
        return False

    print(f"✅ Connecté à Notion en tant que : {bot_name}")
    try:
        db_res = create_database(token, parent_id, "Candidatures")
        save_config(token, db_res)
        print("✅ Base Notion 'Candidatures' configurée avec ses 15 colonnes !")
        return True
    except Exception as e:
        print(f"[!] Erreur lors de la création de la base Notion : {e}")
        return False


def setup_scraping_browsers_interactive() -> bool:
    """Installe le navigateur Chromium requis par le scraping stealth (PASS fonction
    publique, scrape_scrapling.py --stealth). `pip install scrapling[fetchers]` installe
    les paquets Python (patchright/playwright) mais jamais le binaire du navigateur
    lui-même (~300-500 Mo, mis en cache hors du venv) — sans cette étape, --stealth
    échoue à l'exécution avec une erreur "navigateur introuvable", pas au chargement.
    Optionnel et à part (téléchargement volumineux) plutôt qu'automatique et silencieux.
    """
    print("\n" + "=" * 60)
    print("🌐 NAVIGATEUR POUR LE SCRAPING FURTIF (PASS, Optionnel)")
    print("=" * 60)
    print("Nécessaire seulement pour le scraping stealth (offres PASS fonction publique,")
    print("scripts/scrape_scrapling.py --stealth). Téléchargement ~300-500 Mo.")
    ans = input("Installer le navigateur maintenant ? (o/N) : ").strip().lower()
    if ans not in ["o", "oui", "y", "yes"]:
        print("⏩ Ignoré. Si --stealth échoue plus tard : python -m patchright install chromium")
        return False

    res = subprocess.run([sys.executable, "-m", "patchright", "install", "chromium"])
    if res.returncode == 0:
        print("✅ Navigateur installé.")
        return True
    print("[!] Échec de l'installation. Réessayez manuellement : python -m patchright install chromium")
    return False


def setup_gmail_interactive() -> bool:
    print("\n" + "=" * 60)
    print("📧 GMAIL DRAFTS (OAuth 2.0 - Optionnel)")
    print("=" * 60)
    ans = input("Voulez-vous autoriser Gmail pour la génération de brouillons ? (o/N) : ").strip().lower()
    if ans not in ["o", "oui", "y", "yes"]:
        print("⏩ Configuration Gmail ignorée.")
        return False

    creds_file = os.path.join(ROOT, "config", "credentials.json")
    if not os.path.isfile(creds_file):
        print(f"\n[!] Fichier d'identifiants Google manquant : {creds_file}")
        print("Pour activer Gmail :")
        print("  1. Créez un OAuth Client ID (type 'Desktop App') sur Google Cloud Console.")
        print("  2. Téléchargez le fichier JSON et placez-le sous 'config/credentials.json'.")
        print("  3. Lancez : python scripts/auth_gmail.py")
        return False

    print("Lancement du flux OAuth dans votre navigateur...")
    res = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "auth_gmail.py")])
    return res.returncode == 0


def init_state_dirs() -> None:
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "outputs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)

    seen_file = os.path.join(ROOT, "state", "seen.json")
    if not os.path.isfile(seen_file):
        with open(seen_file, "w", encoding="utf-8") as f:
            json.dump([], f)

    qa_file = os.path.join(ROOT, "state", "qa-memory.json")
    if not os.path.isfile(qa_file):
        with open(qa_file, "w", encoding="utf-8") as f:
            json.dump({}, f)

    for folder in ["state", "outputs", "logs"]:
        keep = os.path.join(ROOT, folder, ".gitkeep")
        if not os.path.isfile(keep):
            open(keep, "a").close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialisation du Job-Hunt Kit")
    parser.add_argument("--fichier", "--profile", help="Fichier JSON de profil pré-rempli")
    parser.add_argument("--theme", help="Thème (navy, emerald, bordeaux ou hex #HEX)")
    parser.add_argument("--notion-token", help="Token Notion Integration")
    parser.add_argument("--notion-page-url", help="URL de la page parente Notion")
    parser.add_argument("--skip-deps", action="store_true", help="Ignorer l'installation des dépendances pip")
    parser.add_argument("--skip-gmail", action="store_true", help="Ignorer la configuration Gmail")
    parser.add_argument("--skip-notion", action="store_true", help="Ignorer la configuration Notion")
    parser.add_argument("--force", action="store_true", help="Écraser sans confirmation les fichiers existants")
    parser.add_argument("--non-interactive", action="store_true", help="Mode non-interactif (batch)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🚀 INITIALISATION DU JOB-HUNT KIT")
    print("=" * 60)

    # 1. Vérifications système
    py_ok = check_python_version()
    chrome_path = check_chrome()
    deps_ok = check_and_install_deps(args.skip_deps)
    init_state_dirs()

    # 2. Profil
    cv_data_path = os.path.join(ROOT, "templates", "cv", "cv-data.json")
    if args.fichier and os.path.isfile(args.fichier):
        create_profile_from_file(args.fichier)
    elif os.path.isfile(cv_data_path) and not args.force:
        if args.non_interactive:
            print("ℹ️ cv-data.json existant conservé.")
        else:
            ans = input(f"\nUn profil existe déjà ({cv_data_path}). Conserver ce profil ? (O/n) : ").strip().lower()
            if ans in ["n", "non", "no"]:
                prompt_questionnaire()
            else:
                print("✅ Profil existant conservé.")
    else:
        if args.non_interactive:
            # En non-interactif sans fichier, copie le template si absent
            if not os.path.isfile(cv_data_path):
                tmpl = os.path.join(ROOT, "templates", "cv", "cv-data.template.json")
                shutil.copy(tmpl, cv_data_path)
        else:
            prompt_questionnaire()

    # 3. Thème
    if args.theme:
        apply_theme(args.theme)
    elif not args.non_interactive:
        print("\n--- Choix du Thème Graphique (CV & Lettre) ---")
        print("  [1] Navy (#323B4C - Classique élégant, défaut)")
        print("  [2] Émeraude (#155E4C - Moderne & impactant)")
        print("  [3] Bordeaux (#7A1F2B - Institutionnel & sobre)")
        print("  [4] Couleur hexadécimale personnalisée")
        ch = input("Votre choix (1/2/3/4) [1] : ").strip()
        if ch == "2":
            apply_theme("emerald")
        elif ch == "3":
            apply_theme("bordeaux")
        elif ch == "4":
            hex_c = input("Entrez votre code couleur hex (ex: #1E40AF) : ").strip()
            apply_theme(hex_c)
        else:
            apply_theme("navy")
    else:
        apply_theme("navy")

    # 4. Notion
    notion_ok = False
    if args.notion_token and args.notion_page_url:
        from init_notion_db import create_database, parse_id, save_config, test_token
        parent_id = parse_id(args.notion_page_url)
        ok, _ = test_token(args.notion_token)
        if ok:
            db_res = create_database(args.notion_token, parent_id, "Candidatures")
            save_config(args.notion_token, db_res)
            notion_ok = True
    elif not args.skip_notion and not args.non_interactive:
        notion_ok = setup_notion_interactive()

    # 5. Gmail
    gmail_ok = False
    token_gmail = os.path.join(ROOT, "config", "gmail_token.json")
    if os.path.isfile(token_gmail):
        gmail_ok = True
    elif not args.skip_gmail and not args.non_interactive:
        gmail_ok = setup_gmail_interactive()

    # 5bis. Navigateur pour le scraping stealth (optionnel, téléchargement volumineux).
    # Pas de vérification de présence ici : le paquet patchright (Python) et le binaire
    # navigateur (cache hors venv, ~300-500 Mo) sont deux choses indépendantes, et il n'y
    # a pas de moyen fiable/rapide de vérifier le second sans tenter un vrai lancement.
    browsers_ok = False
    if not args.non_interactive:
        browsers_ok = setup_scraping_browsers_interactive()

    # 6. Bilan récapitulatif
    print("\n" + "=" * 60)
    print("📋 BILAN DE L'INITIALISATION")
    print("=" * 60)
    print(f"  [{'✅' if py_ok else '❌'}] Python 3.9+ ({sys.version.split()[0]})")
    print(f"  [{'✅' if chrome_path else '⚠️'}] Moteur d'impression PDF ({chrome_path or 'Chrome/Edge introuvable - définir CHROME_PATH'})")
    print(f"  [{'✅' if deps_ok else '❌'}] Dépendances Python")
    print(f"  [{'✅' if os.path.isfile(cv_data_path) else '❌'}] Profil CV (templates/cv/cv-data.json)")
    print(f"  [{'✅' if notion_ok or os.path.isfile(os.path.join(ROOT, 'config', '.notion_token')) else '⚪'}] Base Notion")
    print(f"  [{'✅' if gmail_ok else '⚪'}] Envoi automatique Gmail (OAuth)")
    print(f"  [{'✅' if browsers_ok else '⚪'}] Navigateur scraping furtif (patchright install chromium)")

    print("\n🎉 Le Job-Hunt Kit est prêt à l'emploi !")
    print("Commandes utiles :")
    print("  - Construire un CV test : python scripts/render_cv.py --profile alternance --pdf")
    print("  - Scraper les offres PASS : python scripts/scrape_pass.py")
    print("  - Générer un zip de partage : python scripts/make_kit.py\n")


if __name__ == "__main__":
    main()
