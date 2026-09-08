#!/usr/bin/env python3
"""Pousse les offres en attente vers Notion via l'API REST (sans MCP).

Permet au Radar planifié (qui n'a pas le MCP Notion) d'écrire quand même dans la base,
en autonomie. Lit le token d'intégration Notion depuis :
  - la variable d'environnement NOTION_TOKEN, ou
  - le fichier config/.notion_token (une ligne, non versionné, à garder secret).

Lit state/pending-notion-upsert.json, déduplique par "Lien offre" contre la base,
crée les pages manquantes, puis vide la file.

Usage:
  python scripts/push_notion.py [--dry-run]

Prérequis (une fois) :
  1. Créer une intégration interne sur https://www.notion.so/my-integrations (token ntn_... / secret_...).
  2. Partager la base "Candidatures Data/IA" avec l'intégration (menu ... > Connexions).
  3. Mettre le token dans config/.notion_token ou l'env NOTION_TOKEN.
"""
import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

from typing import Any, Dict, List, Optional, Set, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netutil import with_retries

NOTION_VERSION: str = "2022-06-28"


def load_cfg() -> Dict[str, Any]:
    with open(os.path.join(ROOT, "config", "notion.json"), "r", encoding="utf-8") as f:
        return json.load(f)


DATABASE_ID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def database_id_from_url(url: str) -> str:
    # https://app.notion.com/p/3b437a76d2a7451694a03c28680b630b -> UUID
    frag = url.rstrip("/").split("/")[-1].split("?")[0].split("-")[-1]
    frag = frag[-32:]
    db_id = "-".join([frag[0:8], frag[8:12], frag[12:16], frag[16:20], frag[20:32]])
    if not DATABASE_ID_RE.match(db_id):
        # Corrigé le 2026-09-08 : avec le placeholder de config/notion.template.json
        # ("https://www.notion.so/<votre-base>"), cette fonction renvoyait silencieusement
        # un ID corrompu ("base>----") au lieu d'un id Notion — la vraie erreur (Notion
        # jamais configuré) n'apparaissait qu'ensuite, cryptique, dans la réponse de
        # l'API Notion. Erreur claire ici, au bon endroit.
        sys.exit(
            f"URL de base Notion invalide : {url!r}. Notion n'est probablement pas encore "
            "configuré — lancez python scripts/init.py ou python scripts/init_notion_db.py "
            "--token <token> --page-url <url>."
        )
    return db_id


def get_token() -> str:
    tok = os.environ.get("NOTION_TOKEN")
    if tok:
        return tok.strip()
    path = os.path.join(ROOT, "config", ".notion_token")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    sys.exit("Token Notion manquant : mets-le dans env NOTION_TOKEN ou config/.notion_token")


def api(method: str, url: str, token: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")

    def _do() -> Dict[str, Any]:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        # N4 (audit 2026-09-07) : retente les erreurs transitoires (timeout, 5xx) avant
        # d'abandonner. Un 4xx (token invalide, mauvaise requête) n'est jamais transitoire
        # -> échoue immédiatement, pas de délai inutile.
        return with_retries(_do)
    except urllib.error.HTTPError as e:
        sys.exit(f"Notion API {e.code}: {e.read().decode('utf-8')}")


def norm_key(s: str) -> str:
    """Normalise pour comparaison texte : minuscule, sans accents, espaces compactés."""
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode("utf-8")
    return " ".join(s.lower().split())


def find_similar_existing(
    pages: List[Dict[str, Any]], entreprise: str, poste: str,
    entreprise_threshold: float = 0.9, poste_threshold: float = 0.7,
) -> Optional[Tuple[Dict[str, Any], float]]:
    """Détection de quasi-doublon (N3, cf. plan d'amélioration) par similarité texte —
    complète la dédup stricte par URL (`existing_links`), qui rate deux offres identiques
    reformulées différemment ou republiées sous un lien différent. Aucune dépendance
    supplémentaire (difflib, stdlib).

    Compare entreprise et poste SÉPARÉMENT plutôt qu'en chaîne concaténée : sur une chaîne
    unique, « Doctolib Data Scientist » vs « Doctolib Data Engineer » (deux offres bien
    distinctes) ressort presque aussi similaire que « Doctolib AI Data Engineer / DataOps »
    vs « ...DataOps (Réf: 123) » (la même offre republiée) — vérifié à la main lors de
    l'écriture (0.756 vs 0.795), la marge est trop fine pour un seuil unique fiable. Exiger
    une entreprise quasi-identique (>= 0.9) ET un poste significativement similaire (>= 0.7)
    sépare nettement les deux cas (poste seul : 0.74 pour le doublon réel, 0.43-0.59 pour de
    vrais postes différents).

    Un signal à afficher, jamais une décision automatique de sauter l'offre : mieux vaut un
    doublon visible qu'une vraie offre silencieusement ignorée sur un faux positif."""
    ent_norm, poste_norm = norm_key(entreprise), norm_key(poste)
    best: Optional[Dict[str, Any]] = None
    best_ratio = 0.0
    for pg in pages:
        props = pg.get("properties", {})
        cand_ent = norm_key(prop_text(props, "Entreprise"))
        cand_poste = norm_key(prop_text(props, "Poste"))
        if not cand_ent or not cand_poste:
            continue
        ent_ratio = difflib.SequenceMatcher(None, ent_norm, cand_ent).ratio()
        if ent_ratio < entreprise_threshold:
            continue
        poste_ratio = difflib.SequenceMatcher(None, poste_norm, cand_poste).ratio()
        if poste_ratio >= poste_threshold and poste_ratio > best_ratio:
            best_ratio, best = poste_ratio, pg
    if best is not None:
        return best, best_ratio
    return None


def prop_text(props: Dict[str, Any], name: str) -> str:
    """Lit une propriété title/rich_text Notion en texte brut."""
    v = props.get(name, {})
    t = v.get("type")
    if t == "title":
        return "".join(x["plain_text"] for x in v.get("title", []))
    if t == "rich_text":
        return "".join(x["plain_text"] for x in v.get("rich_text", []))
    return ""


def prop_select(props: Dict[str, Any], name: str) -> str:
    """Lit une propriété select Notion (nom de l'option, ou chaîne vide)."""
    return ((props.get(name, {}) or {}).get("select") or {}).get("name", "")


def prop_date(props: Dict[str, Any], name: str) -> Optional[str]:
    """Lit la date de début d'une propriété date Notion (ISO), ou None."""
    return ((props.get(name, {}) or {}).get("date") or {}).get("start")


def prop_url(props: Dict[str, Any], name: str) -> str:
    """Lit une propriété url Notion, ou chaîne vide."""
    return (props.get(name, {}) or {}).get("url") or ""


def fetch_all_pages(token: str, db_id: str) -> List[Dict[str, Any]]:
    """Pagine l'intégralité d'une base Notion et renvoie les pages brutes (avec properties)."""
    pages: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        body: Dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = api("POST", f"https://api.notion.com/v1/databases/{db_id}/query", token, body)
        pages.extend(res.get("results", []))
        if res.get("has_more"):
            cursor = res.get("next_cursor")
        else:
            break
    return pages


def existing_links(token: str, db_id: str) -> Set[str]:
    links: Set[str] = set()
    for pg in fetch_all_pages(token, db_id):
        prop = pg.get("properties", {}).get("Lien offre", {})
        if prop.get("url"):
            links.add(prop["url"])
    return links


def find_page_by_entreprise_poste(token: str, db_id: str, entreprise: str, poste: str) -> Optional[str]:
    """Retrouve une page par Entreprise+Poste quand le lien d'offre (clé habituelle) est
    inconnu — cas de state/outreach.json créé avant que le champ 'lien' n'y soit tracé.
    Ne renvoie un id que si le match est unique : mieux vaut ne rien mettre à jour que
    deviner et écrire sur la mauvaise offre."""
    body: Dict[str, Any] = {
        "filter": {
            "and": [
                {"property": "Entreprise", "title": {"equals": entreprise}},
                {"property": "Poste", "rich_text": {"contains": poste[:80]}},
            ]
        },
        "page_size": 5,
    }
    res = api("POST", f"https://api.notion.com/v1/databases/{db_id}/query", token, body)
    results = res.get("results", [])
    return results[0]["id"] if len(results) == 1 else None


def offer_to_props(o: Dict[str, Any]) -> Dict[str, Any]:
    tag = {"auto": "[AUTO] ", "captcha": "[CAPTCHA] ", "login": "[LOGIN] "}.get(o.get("autonomie", ""), "")
    notes = tag + o.get("notes_matching", "")
    p: Dict[str, Any] = {
        "Entreprise": {"title": [{"text": {"content": o["entreprise"]}}]},
        "Poste": {"rich_text": [{"text": {"content": o.get("poste", "")}}]},
        "Type": {"select": {"name": "Alternance" if o.get("type") == "alternance" else "Stage"}},
        "Statut": {"select": {"name": o.get("statut", "À traiter")}},
        "Lien offre": {"url": o.get("lien")},
        "Source": {"select": {"name": o.get("source", "Autre")}},
        "Lieu": {"rich_text": [{"text": {"content": o.get("lieu", "")}}]},
        "Score": {"number": o.get("score")},
        "Notes matching": {"rich_text": [{"text": {"content": notes}}]},
    }
    ats = o.get("ats")
    if ats:
        p["ATS"] = {"select": {"name": ats.capitalize() if ats.lower() != "wttj" else "Autre"}}
    if o.get("contact_recruteur"):
        p["Contact recruteur"] = {"email": o["contact_recruteur"]}
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_cfg()
    db_id = database_id_from_url(cfg["database_url"])
    pending_path = os.path.join(ROOT, "state", "pending-notion-upsert.json")
    if not os.path.isfile(pending_path):
        print("Aucun fichier en attente (state/pending-notion-upsert.json).")
        return

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)
    offres = pending.get("offres", [])
    if not offres:
        print("Rien à pousser.")
        return

    token = get_token()
    pages = fetch_all_pages(token, db_id)
    have = {prop_url(pg.get("properties", {}), "Lien offre") for pg in pages} - {""}
    created, skipped, doublons_possibles = 0, 0, 0
    for o in offres:
        if o.get("lien") in have:
            skipped += 1
            continue
        # N3 : signal de quasi-doublon (texte similaire, lien différent) — jamais un skip
        # automatique, juste une alerte à côté de la création.
        similar = find_similar_existing(pages, o.get("entreprise", ""), o.get("poste", ""))
        if similar:
            doublons_possibles += 1
            _, ratio = similar
            print(f"  ⚠️  Quasi-doublon possible ({ratio:.0%} similaire) : {o['entreprise']} - {o.get('poste')}")
        if args.dry_run:
            print("[dry-run] créerait:", o["entreprise"], "-", o.get("poste"))
            created += 1
            continue
        api("POST", "https://api.notion.com/v1/pages", token,
            {"parent": {"database_id": db_id}, "properties": offer_to_props(o)})
        created += 1
    print(f"Notion : {created} créées, {skipped} déjà présentes, {doublons_possibles} quasi-doublon(s) signalé(s).")

    if not args.dry_run:
        pending["offres"] = []
        with open(pending_path, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
