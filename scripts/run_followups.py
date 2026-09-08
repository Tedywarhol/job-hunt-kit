#!/usr/bin/env python3
"""Moteur de relances recruteur : J+3/J+5/J+7/J+10, détection de réponse.

Mode **brouillons uniquement** : ce script ne fait jamais d'envoi automatique.
Il crée des brouillons Gmail pour les relances dues, jamais un `send`. C'est
la Brique M1 de docs/plans/2026-09-07-plan-amelioration.md — elle comble le
vide identifié dans l'analyse du 2026-09-07 (séquences bloquées à J+0, aucune
relance partie automatiquement).

Pour chaque candidature de state/outreach.json dont l'étape n'est pas
terminale (Terminé, Réponse reçue) :
  1. Vérifie d'abord une éventuelle réponse du recruteur dans Gmail (recherche
     par expéditeur + date, faute de thread_id connu au moment du J+0). Une
     réponse trouvée arrête la séquence immédiatement, quelle que soit
     l'échéance — priorité absolue sur toute relance.
  2. Si l'échéance de la prochaine étape (J+3/5/7/10) est atteinte et qu'aucune
     réponse n'a été trouvée : crée un brouillon Gmail pour cette étape,
     avance l'étape dans state/outreach.json et (si possible) dans Notion.
  3. Après J+10 sans réponse : étape "Terminé".

Un échec de vérification Gmail (API, réseau) ne doit JAMAIS être traité comme
« pas de réponse » : la candidature est alors ignorée ce run-là plutôt que de
risquer une relance envoyée à quelqu'un qui a déjà répondu (voir find_reply
dans create_gmail_draft.py).

Usage:
  python scripts/run_followups.py            # dry-run : affiche les actions, n'écrit rien
  python scripts/run_followups.py --apply    # applique réellement (brouillons + state + Notion)
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from create_gmail_draft import create_draft, find_reply, get_gmail_service
from logutil import log_error
from profile import load_personal
import notion_apply as na
import push_notion as pn

OUTREACH_PATH: str = os.path.join(ROOT, "state", "outreach.json")

SEQUENCE: List[str] = ["J+0", "J+3", "J+5", "J+7", "J+10"]
DELAIS_JOURS: Dict[str, int] = {"J+3": 3, "J+5": 5, "J+7": 7, "J+10": 10}

# Reprend fidèlement config/outreach-templates.md (ton court, pas de tiret cadratin, pas de "&").
TEMPLATES: Dict[str, Dict[str, str]] = {
    "J+3": {
        "objet": "Re: Candidature au poste de {poste}",
        "corps": (
            "Bonjour,\n\n"
            "Je me permets de revenir vers vous au sujet de ma candidature au poste de {poste}. "
            "Mes réalisations récentes recoupent directement les défis techniques et fonctionnels de vos missions.\n\n"
            "Je reste disponible pour en discuter quand cela vous convient.\n\n"
            "Bonne journée,\n{nom}"
        ),
    },
    "J+5": {
        "objet": "Re: Candidature au poste de {poste}",
        "corps": (
            "Bonjour,\n\n"
            "Toujours très motivé par le poste de {poste} chez {entreprise}. Je suis disponible rapidement "
            "et souple sur l'organisation. Mon profil opérationnel me permet d'être immédiatement productif "
            "sur vos projets.\n\n"
            "Je serais heureux d'échanger avec vous.\n\n"
            "Bonne journée,\n{nom}"
        ),
    },
    "J+7": {
        "objet": "Re: Candidature au poste de {poste}",
        "corps": (
            "Bonjour,\n\n"
            "Auriez-vous quelques minutes pour un court échange au sujet du poste de {poste} ? "
            "Je peux m'adapter à votre agenda, par téléphone ou en visio.\n\n"
            "Merci d'avance,\n{nom}"
        ),
    },
    "J+10": {
        "objet": "Re: Candidature au poste de {poste}",
        "corps": (
            "Bonjour,\n\n"
            "Je me permets une dernière relance concernant ma candidature au poste de {poste}. "
            "Si le moment n'est pas opportun, je le comprends tout à fait et reste disponible pour de futures opportunités.\n\n"
            "Merci pour votre temps,\n{nom}"
        ),
    },
}


def next_step(etape: str) -> Optional[str]:
    if etape not in SEQUENCE:
        return None
    idx = SEQUENCE.index(etape)
    return SEQUENCE[idx + 1] if idx + 1 < len(SEQUENCE) else None


def days_since(date_iso: str) -> int:
    d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    return (date.today() - d).days


def anchor_plus(anchor_iso: str, days: int) -> str:
    d = datetime.strptime(anchor_iso, "%Y-%m-%d").date()
    return (d + timedelta(days=days)).isoformat()


def load_outreach() -> List[Dict[str, Any]]:
    if not os.path.isfile(OUTREACH_PATH):
        return []
    with open(OUTREACH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_outreach(entries: List[Dict[str, Any]]) -> None:
    with open(OUTREACH_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def build_relance(etape: str, entreprise: str, poste: str, nom: str) -> Dict[str, str]:
    tpl = TEMPLATES[etape]
    return {
        "objet": tpl["objet"].format(poste=poste),
        "corps": tpl["corps"].format(poste=poste, entreprise=entreprise, nom=nom),
    }


def notion_page_id(token: str, db_id: str, entry: Dict[str, Any]) -> Optional[str]:
    lien = entry.get("lien")
    if lien:
        pid = na.find_page_id(token, db_id, lien)
        if pid:
            return pid
    return pn.find_page_by_entreprise_poste(token, db_id, entry.get("entreprise", ""), entry.get("poste", ""))


def sync_notion(
    token: Optional[str], db_id: Optional[str], entry: Dict[str, Any],
    etape_notion: Optional[str], statut_notion: Optional[str], date_prochaine: Optional[str],
) -> None:
    if not token or not db_id:
        return
    try:
        pid = notion_page_id(token, db_id, entry)
        if not pid:
            log_error(
                f"run_followups: page Notion introuvable/ambiguë pour "
                f"{entry.get('entreprise')} / {entry.get('poste')} (pas de sync)",
                Exception("no unique match"),
            )
            return
        props: Dict[str, Any] = {}
        if etape_notion:
            props["Étape relance"] = {"select": {"name": etape_notion}}
        if statut_notion:
            props["Statut"] = {"select": {"name": statut_notion}}
        props["Date prochaine relance"] = {"date": {"start": date_prochaine} if date_prochaine else None}
        pn.api("PATCH", f"https://api.notion.com/v1/pages/{pid}", token, {"properties": props})
    except Exception as e:
        log_error(f"run_followups: sync Notion {entry.get('entreprise')} / {entry.get('poste')}", e)


def process_entry(
    entry: Dict[str, Any], service: Any, token: Optional[str], db_id: Optional[str], apply_changes: bool,
) -> Dict[str, str]:
    """Traite UNE candidature. Ne lève jamais — toute erreur devient un résultat 'échec' loggé."""
    result: Dict[str, str] = {
        "entreprise": str(entry.get("entreprise", "?")), "poste": str(entry.get("poste", "?")),
        "action": "aucune", "detail": "",
    }
    etape = entry.get("etape", "J+0")
    if etape in ("Terminé", "Réponse reçue"):
        result["detail"] = "séquence déjà close"
        return result

    email = entry.get("email")
    anchor = entry.get("date_j0") or entry.get("date_creation_brouillon")
    if not email or not anchor:
        result["action"] = "ignorée"
        result["detail"] = "entrée incomplète (email ou date d'ancrage manquant)"
        return result
    entry.setdefault("date_j0", anchor)

    # 1) Réponse ? Priorité absolue, indépendamment de l'échéance.
    try:
        thread_id = find_reply(service, email, anchor)
    except Exception as e:
        log_error(f"run_followups: vérification réponse Gmail pour {email}", e)
        result["action"] = "ignorée"
        result["detail"] = "échec de vérification Gmail (logs/errors.log) — aucune action, par sécurité"
        return result

    if thread_id:
        result["action"] = "réponse détectée"
        result["detail"] = f"séquence arrêtée (thread {thread_id})"
        if apply_changes:
            entry["etape"] = "Réponse reçue"
            entry["statut"] = "Réponse reçue"
            entry["thread_id"] = thread_id
            sync_notion(token, db_id, entry, etape_notion="Réponse reçue", statut_notion="Réponse reçue", date_prochaine=None)
        return result

    # 2) Étape suivante et échéance.
    nxt = next_step(etape)
    if not nxt:
        result["action"] = "clôturée"
        result["detail"] = "J+10 dépassé sans réponse"
        if apply_changes:
            entry["etape"] = "Terminé"
            entry["statut"] = "Terminé"
            sync_notion(token, db_id, entry, etape_notion="Terminé", statut_notion=None, date_prochaine=None)
        return result

    due_days = DELAIS_JOURS[nxt]
    elapsed = days_since(anchor)
    if elapsed < due_days:
        result["detail"] = f"échéance {nxt} dans {due_days - elapsed} j"
        return result

    # 3) Échéance atteinte, pas de réponse -> brouillon de relance.
    personal = load_personal()
    relance = build_relance(nxt, str(entry.get("entreprise", "")), str(entry.get("poste", "")), personal.get("nom", ""))
    if not apply_changes:
        result["action"] = f"préparerait un brouillon {nxt}"
        result["detail"] = relance["objet"]
        return result

    try:
        draft = create_draft(service, email, relance["objet"], relance["corps"], from_email=personal.get("email"))
    except Exception as e:
        log_error(f"run_followups: création brouillon {nxt} pour {email}", e)
        result["action"] = "échec"
        result["detail"] = "création du brouillon Gmail a échoué (logs/errors.log)"
        return result

    entry.setdefault("relances", []).append(
        {"etape": nxt, "date": date.today().isoformat(), "brouillon_id": draft.get("id"), "statut": "Brouillon créé"}
    )
    entry["etape"] = nxt
    entry["statut"] = "Brouillon créé"
    entry["brouillon_id"] = draft.get("id")
    result["action"] = f"brouillon {nxt} créé"
    result["detail"] = f"id={draft.get('id')}"

    apres = next_step(nxt)
    date_prochaine = anchor_plus(anchor, DELAIS_JOURS[apres]) if apres else None
    sync_notion(token, db_id, entry, etape_notion=nxt, statut_notion=None, date_prochaine=date_prochaine)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Moteur de relances recruteur (J+3/5/7/10). Mode brouillons uniquement : "
        "aucun email n'est jamais envoyé automatiquement par ce script."
    )
    ap.add_argument("--apply", action="store_true", help="Applique réellement (sinon dry-run : affiche sans rien écrire).")
    args = ap.parse_args()

    entries = load_outreach()
    if not entries:
        print("state/outreach.json vide ou introuvable — rien à relancer.")
        return

    token: Optional[str] = None
    db_id: Optional[str] = None
    try:
        cfg = pn.load_cfg()
        db_id = pn.database_id_from_url(cfg["database_url"])
        token = pn.get_token()
    except SystemExit as e:
        print(f"[info] Notion non configuré, synchronisation ignorée : {e}", file=sys.stderr)

    service = get_gmail_service()

    mode = "[APPLY]" if args.apply else "[DRY-RUN]"
    print(f"{mode} Moteur de relances — {len(entries)} candidature(s) suivie(s)\n")
    for entry in entries:
        r = process_entry(entry, service, token, db_id, apply_changes=args.apply)
        suffix = f" — {r['detail']}" if r["detail"] else ""
        print(f"  - {r['entreprise']} / {r['poste']} : {r['action']}{suffix}")

    if args.apply:
        save_outreach(entries)
        print("\nstate/outreach.json mis à jour.")
    else:
        print("\nAucune modification écrite (dry-run). Relancez avec --apply pour agir réellement.")
    print("Rappel : mode brouillons uniquement, aucun envoi automatique tant que ce n'est pas explicitement changé.")


if __name__ == "__main__":
    main()
