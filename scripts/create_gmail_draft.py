#!/usr/bin/env python3
"""Crée un brouillon dans Gmail (avec le CV en pièce jointe) via l'API Gmail.

Usage:
  python scripts/create_gmail_draft.py \
      --to "recruteur@organisme.gouv.fr" \
      --subject "Candidature Alternance 24 mois — Chef de projet IA" \
      --body-file "chemin/vers/lettre.txt" \
      --cv "outputs/CV_Prenom_NOM_Alternance.pdf"

Prérequis Google OAuth (une seule fois) :
  1. Activer l'API Gmail sur Google Cloud Console (console.cloud.google.com).
  2. Créer un identifiant OAuth Client ID (type 'Application pour ordinateur' / Desktop app).
  3. Télécharger le fichier JSON et le placer sous 'config/credentials.json' (gitignoré).
  4. Au premier lancement, une page s'ouvre dans le navigateur pour autoriser l'accès à
     l'adresse Gmail du candidat (personal.email dans templates/cv/cv-data.json).
  5. Le token est sauvegardé dans 'config/gmail_token.json' (gitignoré).
"""
import argparse
import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import sys

from typing import Any, Dict, List, Optional, Union

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from profile import doc_base_names, load_personal

SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service() -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Les bibliothèques Google API sont requises. Installez-les avec :\n"
            "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds: Optional[Credentials] = None
    token_path: str = os.path.join(ROOT, "config", "gmail_token.json")
    credentials_path: str = os.path.join(ROOT, "config", "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                sys.exit(
                    f"Fichier manquant : {credentials_path}\n"
                    "Téléchargez vos identifiants OAuth Client ID depuis Google Cloud Console et enregistrez-les dans config/credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_draft(
    service: Any,
    to_email: str,
    subject: str,
    body_text: str,
    attachment_path: Optional[str] = None,
    attachment_paths: Optional[List[str]] = None,
    from_email: Optional[str] = None,
) -> Dict[str, Any]:
    message = MIMEMultipart()
    message["to"] = to_email
    message["subject"] = subject
    sender = from_email or load_personal().get("email", "")
    if sender:
        message["from"] = sender

    # Body
    msg_text = MIMEText(body_text, "plain", "utf-8")
    message.attach(msg_text)

    # Attachments
    all_attachments: List[str] = []
    if attachment_paths:
        all_attachments.extend(attachment_paths)
    if attachment_path and attachment_path not in all_attachments:
        all_attachments.append(attachment_path)

    for att in all_attachments:
        if att and os.path.isfile(att):
            filename = os.path.basename(att)
            with open(att, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
                pdf_part.add_header("Content-Disposition", "attachment", filename=filename)
                message.attach(pdf_part)
            print(f"Pièce jointe ajoutée : {filename}")

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    draft_body = {"message": {"raw": raw_message}}

    draft: Dict[str, Any] = service.users().drafts().create(userId="me", body=draft_body).execute()
    return draft


def find_reply(service: Any, from_emails: Union[str, List[str]], since_iso: str) -> Optional[str]:
    """Cherche un message reçu de l'une des adresses `from_emails` depuis `since_iso` (YYYY-MM-DD).

    Accepte une adresse unique ou une liste (ex. adresse enregistrée + alias de domaine
    connu, cf. `email_alias_connue` dans state/outreach.json) : un recruteur peut répondre
    depuis un domaine différent de celui enregistré au moment de la candidature (ex.
    administrations avec plusieurs domaines @gouv.fr) — bug réel constaté le 2026-09-14
    (refus reçu depuis developpement-durable.gouv.fr, adresse enregistrée mer.gouv.fr,
    jamais détecté faute de recherche sur cette seconde adresse). Toutes les adresses
    fournies sont recherchées en une seule requête Gmail (clause OR).

    Renvoie l'id du thread le plus récent trouvé, ou None si vraiment aucune réponse.
    Utilisé par le moteur de relances pour arrêter une séquence dès qu'un recruteur a
    répondu — faute de thread_id connu à l'avance, on cherche par expéditeur + fenêtre
    de temps. Ne rattrape PAS les erreurs API : un échec de vérification ne doit jamais
    être confondu avec « pas de réponse » (risque de relancer quelqu'un qui a déjà
    répondu) — c'est à l'appelant de décider quoi faire d'un échec (typiquement : ne
    pas agir sur cette candidature ce run-là).
    """
    emails: List[str] = [e for e in ([from_emails] if isinstance(from_emails, str) else from_emails) if e]
    if not emails:
        return None

    since_gmail = since_iso.replace("-", "/")  # Gmail attend after:YYYY/MM/DD
    from_clause = " OR ".join(f"from:{e}" for e in emails)
    query = f"({from_clause}) after:{since_gmail}" if len(emails) > 1 else f"from:{emails[0]} after:{since_gmail}"
    res: Dict[str, Any] = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
    messages = res.get("messages", [])
    return messages[0]["threadId"] if messages else None


def main() -> None:
    personal = load_personal()
    cv_base, _ = doc_base_names(personal)
    default_cv: str = os.path.join(ROOT, "outputs", f"{cv_base}_Alternance.pdf")

    parser = argparse.ArgumentParser(description="Créer un brouillon Gmail avec CV")
    parser.add_argument("--to", required=True, help="Email du destinataire")
    parser.add_argument("--subject", required=True, help="Objet du mail")
    parser.add_argument("--body", help="Texte du message")
    parser.add_argument("--body-file", help="Fichier contenant le texte du message")
    parser.add_argument(
        "--cv",
        default=default_cv,
        help="Chemin vers le CV PDF",
    )
    parser.add_argument(
        "--lettre",
        help="Chemin vers la lettre de motivation PDF (pièce jointe additionnelle, ex. candidature PASS où CV et lettre sont exigés par mail)",
    )
    args = parser.parse_args()

    body_text = args.body or ""
    if args.body_file and os.path.isfile(args.body_file):
        with open(args.body_file, "r", encoding="utf-8") as f:
            body_text = f.read()

    if not body_text:
        sys.exit("Le corps du message (--body ou --body-file) est obligatoire.")

    user_email = personal.get("email", "votre compte")
    print(f"Connexion à l'API Gmail pour {user_email}...")
    service = get_gmail_service()

    attachment_paths = [p for p in [args.cv, args.lettre] if p]
    print(f"Création du brouillon pour {args.to}...")
    draft = create_draft(
        service, args.to, args.subject, body_text,
        attachment_paths=attachment_paths, from_email=personal.get("email"),
    )
    draft_id = draft.get("id")
    print(f"\n✅ Brouillon créé avec succès dans votre boîte Gmail !")
    print(f"ID du brouillon : {draft_id}")
    print(f"Destinataire     : {args.to}")
    print(f"Objet            : {args.subject}")
    print(f"Lien direct      : https://mail.google.com/mail/u/0/#drafts")


if __name__ == "__main__":
    main()
