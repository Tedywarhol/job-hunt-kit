#!/usr/bin/env python3
"""Initialise la base de données Notion 'Candidatures' via l'API REST.

Crée une base avec les 15 colonnes nécessaires, sous une page parente Notion.
Écrit config/notion.json et config/.notion_token.

Usage:
  python scripts/init_notion_db.py --token <ntn_.../secret_...> --page-url <URL_page_parente>
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from typing import Any, Dict, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTION_VERSION: str = "2022-06-28"


def parse_id(s: str) -> str:
    """Extrait un UUID (32 caractères hexadécimaux) depuis une URL ou un ID brut."""
    if not s:
        return ""
    s = s.strip()
    match = re.search(r'([0-9a-fA-F]{32})', s.replace("-", ""))
    if match:
        raw = match.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return s


def api_call(method: str, url: str, token: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            msg = err_json.get("message", err_msg)
        except Exception:
            msg = err_msg
        sys.exit(f"[Erreur API Notion {e.code}] {msg}")
    except urllib.error.URLError as e:
        sys.exit(f"[Erreur Réseau] {e.reason}")


def test_token(token: str) -> Tuple[bool, str]:
    """Vérifie la validité du token avec l'endpoint /v1/users/me."""
    try:
        res = api_call("GET", "https://api.notion.com/v1/users/me", token)
        return True, str(res.get("name", "Bot"))
    except Exception as e:
        return False, str(e)


def create_database(token: str, parent_page_id: str, title: str = "Candidatures") -> Dict[str, Any]:
    properties = {
        "Entreprise": {"title": {}},
        "Poste": {"rich_text": {}},
        "Type": {
            "select": {
                "options": [
                    {"name": "Alternance", "color": "blue"},
                    {"name": "Stage", "color": "green"}
                ]
            }
        },
        "Statut": {
            "select": {
                "options": [
                    {"name": "À traiter", "color": "yellow"},
                    {"name": "Postulé", "color": "blue"},
                    {"name": "Entretien", "color": "purple"},
                    {"name": "Offre reçue", "color": "green"},
                    {"name": "Refusé", "color": "red"},
                    {"name": "Écartée", "color": "gray"}
                ]
            }
        },
        "Lien offre": {"url": {}},
        "Source": {
            "select": {
                "options": [
                    {"name": "WTTJ", "color": "yellow"},
                    {"name": "Indeed", "color": "blue"},
                    {"name": "HelloWork", "color": "orange"},
                    {"name": "PASS", "color": "red"},
                    {"name": "LinkedIn", "color": "blue"},
                    {"name": "Autre", "color": "gray"}
                ]
            }
        },
        "ATS": {
            "select": {
                "options": [
                    {"name": "Teamtailor", "color": "pink"},
                    {"name": "Lever", "color": "green"},
                    {"name": "Greenhouse", "color": "green"},
                    {"name": "Ashby", "color": "purple"},
                    {"name": "WelcomeKit", "color": "yellow"},
                    {"name": "Autre", "color": "gray"}
                ]
            }
        },
        "Lieu": {"rich_text": {}},
        "Score": {"number": {"format": "number"}},
        "Contact recruteur": {"email": {}},
        "Étape relance": {
            "select": {
                "options": [
                    {"name": "J+0", "color": "gray"},
                    {"name": "J+3", "color": "blue"},
                    {"name": "J+5", "color": "yellow"},
                    {"name": "J+7", "color": "orange"},
                    {"name": "J+10", "color": "red"},
                    {"name": "Terminé", "color": "gray"},
                    {"name": "Réponse reçue", "color": "green"}
                ]
            }
        },
        "Date prochaine relance": {"date": {}},
        "Date candidature": {"date": {}},
        "PDF": {"files": {}},
        "Notes matching": {"rich_text": {}}
    }

    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties
    }

    print(f"Création de la base '{title}' dans Notion...")
    res = api_call("POST", "https://api.notion.com/v1/databases", token, body)
    return res


def save_config(token: str, db_data: Dict[str, Any]) -> Tuple[str, str]:
    db_id = db_data["id"]
    db_url = db_data.get("url", f"https://www.notion.so/{db_id.replace('-', '')}")

    token_file = os.path.join(ROOT, "config", ".notion_token")
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(token.strip() + "\n")

    cfg = {
        "database_url": db_url,
        "data_source_id": db_id,
        "collection_url": f"collection://{db_id}",
        "colonnes": {
            "titre": "Entreprise",
            "poste": "Poste",
            "type": "Type",
            "statut": "Statut",
            "lien": "Lien offre",
            "source": "Source",
            "ats": "ATS",
            "lieu": "Lieu",
            "score": "Score",
            "contact": "Contact recruteur",
            "etape_relance": "Étape relance",
            "date_prochaine_relance": "Date prochaine relance",
            "date_candidature": "Date candidature",
            "pdf": "PDF",
            "notes": "Notes matching"
        }
    }

    cfg_file = os.path.join(ROOT, "config", "notion.json")
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    return token_file, cfg_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialiser la base Notion Candidatures")
    parser.add_argument("--token", help="Token d'intégration Notion (ntn_... ou secret_...)")
    parser.add_argument("--page-url", help="URL ou ID de la page Notion parente")
    parser.add_argument("--title", default="Candidatures", help="Titre de la base (défaut: Candidatures)")
    args = parser.parse_args()

    token = args.token or os.environ.get("NOTION_TOKEN")
    if not token:
        token_path = os.path.join(ROOT, "config", ".notion_token")
        if os.path.isfile(token_path):
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()

    if not token:
        sys.exit("Token Notion manquant. Fournissez --token <token> ou configurez config/.notion_token")

    if not args.page_url:
        sys.exit("URL de la page parente manquante. Fournissez --page-url <url>")

    parent_id = parse_id(args.page_url)
    if not parent_id:
        sys.exit(f"Impossible d'extraire l'ID de page depuis '{args.page_url}'")

    ok, bot_name = test_token(token)
    if not ok:
        sys.exit(f"Token Notion invalide : {bot_name}")
    print(f"✅ Connecté à Notion en tant que : {bot_name}")

    db_res = create_database(token, parent_id, args.title)
    tok_f, cfg_f = save_config(token, db_res)

    print(f"\n✅ Base Notion créée avec succès !")
    print(f"  - Nom        : {args.title}")
    print(f"  - ID         : {db_res['id']}")
    print(f"  - URL        : {db_res.get('url')}")
    print(f"  - Config     : {cfg_f}")
    print(f"  - Token sauv : {tok_f}")


if __name__ == "__main__":
    main()
