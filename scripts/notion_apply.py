#!/usr/bin/env python3
"""File de candidatures Notion + marquage du statut, via l'API REST (token config/.notion_token).

Sous-commandes :
  list                     -> liste les offres Statut="À traiter", triées par Score décroissant.
  mark --url <lien> --statut Postulé [--date YYYY-MM-DD] [--notes "..."]
                           -> met à jour le statut (et la date de candidature) de l'offre.

Réutilise le token + l'accès DB de push_notion.py.
"""
import argparse
import json
import os
import sys

from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push_notion as pn  # get_token, database_id_from_url, api, load_cfg


def query_a_traiter(token: str, db_id: str) -> List[Dict[str, Any]]:
    body = {
        "filter": {"property": "Statut", "select": {"equals": "À traiter"}},
        "sorts": [{"property": "Score", "direction": "descending"}],
        "page_size": 100,
    }
    res: Dict[str, Any] = pn.api("POST", f"https://api.notion.com/v1/databases/{db_id}/query", token, body)
    out: List[Dict[str, Any]] = []
    for pg in res.get("results", []):
        p = pg.get("properties", {})
        def txt(name: str) -> str:
            v = p.get(name, {})
            if v.get("type") == "title":
                return "".join(t["plain_text"] for t in v.get("title", []))
            if v.get("type") == "rich_text":
                return "".join(t["plain_text"] for t in v.get("rich_text", []))
            return ""
        out.append({
            "id": pg["id"],
            "entreprise": txt("Entreprise"),
            "poste": txt("Poste"),
            "type": (p.get("Type", {}).get("select") or {}).get("name", ""),
            "lien": p.get("Lien offre", {}).get("url", ""),
            "ats": (p.get("ATS", {}).get("select") or {}).get("name", ""),
            "score": p.get("Score", {}).get("number"),
            "contact": p.get("Contact recruteur", {}).get("email"),
            "notes": txt("Notes matching"),
        })
    return out


def find_page_id(token: str, db_id: str, url: str) -> Optional[str]:
    body = {"filter": {"property": "Lien offre", "url": {"equals": url}}, "page_size": 1}
    res: Dict[str, Any] = pn.api("POST", f"https://api.notion.com/v1/databases/{db_id}/query", token, body)
    r = res.get("results", [])
    return r[0]["id"] if r else None


def cmd_list(token: str, db_id: str) -> None:
    offers = query_a_traiter(token, db_id)
    print(json.dumps(offers, ensure_ascii=False, indent=2))
    print(f"\n{len(offers)} offre(s) 'À traiter'.", file=sys.stderr)


def cmd_mark(token: str, db_id: str, url: str, statut: str, date: Optional[str], notes: Optional[str]) -> None:
    pid = find_page_id(token, db_id, url)
    if not pid:
        sys.exit(f"Offre introuvable pour l'URL: {url}")
    props: Dict[str, Any] = {"Statut": {"select": {"name": statut}}}
    if date:
        props["Date candidature"] = {"date": {"start": date}}
    if notes:
        props["Notes matching"] = {"rich_text": [{"text": {"content": notes}}]}
    pn.api("PATCH", f"https://api.notion.com/v1/pages/{pid}", token, {"properties": props})
    print(f"OK: {url} -> Statut={statut}" + (f", Date={date}" if date else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    m = sub.add_parser("mark")
    m.add_argument("--url", required=True)
    m.add_argument("--statut", default="Postulé")
    m.add_argument("--date", default=None, help="YYYY-MM-DD")
    m.add_argument("--notes", default=None)
    args = ap.parse_args()

    cfg = pn.load_cfg()
    db_id = pn.database_id_from_url(cfg["database_url"])
    token = pn.get_token()

    if args.cmd == "list":
        cmd_list(token, db_id)
    elif args.cmd == "mark":
        cmd_mark(token, db_id, args.url, args.statut, args.date, args.notes)


if __name__ == "__main__":
    main()
