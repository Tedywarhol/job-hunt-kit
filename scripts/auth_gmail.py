#!/usr/bin/env python3
"""Script d'authentification Google OAuth propre pour Gmail."""
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from typing import Any, List

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.modify"]


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path: str = os.path.join(ROOT, "config", "credentials.json")
    token_path: str = os.path.join(ROOT, "config", "gmail_token.json")
    url_file: str = os.path.join(ROOT, "config", "auth_url.txt")

    if not os.path.isfile(credentials_path):
        sys.exit(f"Fichier manquant : {credentials_path}")

    print("Initialisation du flux OAuth...")
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=SCOPES)

    prompt_template: str = (
        "\n" + "=" * 75 + "\n"
        "CLIQUEZ SUR CE LIEN POUR AUTORISER GMAIL :\n"
        "{url}\n"
        + "=" * 75 + "\n"
    )

    def custom_format(url: str) -> str:
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(url)
        return prompt_template.format(url=url)

    prompt_obj = type("Prompt", (), {"format": lambda self, url: custom_format(url)})()

    print("Démarrage du serveur et génération du lien...")
    creds = flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message=prompt_obj,
        success_message="Authentification réussie ! Vous pouvez fermer cette page.",
        open_browser=True,
    )

    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"\n✅ Authentification réussie ! Token sauvegardé dans {token_path}")
    if os.path.exists(url_file):
        try:
            os.remove(url_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
