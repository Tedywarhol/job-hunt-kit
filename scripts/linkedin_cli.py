#!/usr/bin/env python3
"""Client MCP minimal et en LECTURE SEULE pour le serveur LinkedIn du kit.

Pourquoi : les outils `mcp__mcp-server-linkedin__*` n'existent dans Claude Code que si `.mcp.json` est présent et
approuvé au démarrage de la session. Quand ce n'est pas le cas (12 octobre 2026 : le fichier local avait disparu),
ce script lance le même serveur en sous-processus (session LinkedIn déjà enregistrée dans `~/.linkedin-mcp`) et
appelle ses outils de lecture. Aucun outil d'écriture n'est autorisé : ni `connect_with_person`, ni l'édition de
profil, ni la messagerie.

Prérequis : un interpréteur où le paquet `mcp` est installé (le venv de `.linkedin-mcp-fork/` convient).

Usage :
  python scripts/linkedin_cli.py outils
  python scripts/linkedin_cli.py appel search_people '{"keywords": "responsable data Forvia", "location": "France"}'
  python scripts/linkedin_cli.py lot travaux.json sortie.json     # [{"id", "outil", "args"}, ...]
Variable facultative : LINKEDIN_MCP_COMMAND (commande du serveur ; sinon le serveur du fork local, puis `uvx`).

Astuces de recherche (vérifiées le 2026-10-12) :
  - `date_posted` accepte aussi `r<secondes>` (transmis tel quel à LinkedIn) : "r262800" = 73 heures exactement,
    alors que les valeurs nommées s'arrêtent à past_hour, past_24_hours, past_week, past_month.
  - `keywords` accepte la syntaxe booléenne de LinkedIn : '(alternance OR alternant) AND (data OR "machine learning")'.
    Sans cela, LinkedIn mélange stages, CDI et télétravail et ne charge qu'environ 50 cartes.
  - Un lieu écrit « Île-de-France, France » est lu comme « France entière » ; écrire « Île-de-France » seul.
"""
import asyncio
import json
import os
import random
import shlex
import sys
from typing import Any, Dict, List, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTILS_LECTURE = {"search_jobs", "get_job_details", "search_people", "get_person_profile", "get_company_profile",
                  "get_company_posts", "search_companies", "get_company_employees", "get_saved_jobs",
                  "get_sidebar_profiles"}
PAUSE_ENTRE_APPELS = (4.0, 8.0)  # secondes : rythme raisonnable envers LinkedIn
DELAI_MAX_APPEL = 240.0


def outil_autorise(nom: str) -> bool:
    return nom in OUTILS_LECTURE


def commande_serveur() -> Tuple[str, List[str]]:
    """Commande du serveur MCP : variable d'environnement, sinon le fork local, sinon uvx."""
    if os.environ.get("LINKEDIN_MCP_COMMAND"):
        morceaux = shlex.split(os.environ["LINKEDIN_MCP_COMMAND"], posix=False)
        return morceaux[0], morceaux[1:]
    fork = os.path.join(ROOT, ".linkedin-mcp-fork", ".venv", "Scripts", "mcp-server-linkedin.exe")
    if os.path.isfile(fork):
        return fork, []
    return "uvx", ["mcp-server-linkedin@latest"]


async def appeler(session: ClientSession, outil: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if not outil_autorise(outil):
        return {"ok": False, "erreur": f"outil refusé (lecture seule) : {outil}"}
    try:
        res = await asyncio.wait_for(session.call_tool(outil, args), timeout=DELAI_MAX_APPEL)
    except Exception as e:  # noqa: BLE001 - consigné dans le résultat, jamais avalé
        return {"ok": False, "erreur": str(e)[:300]}
    texte = "\n".join(c.text for c in res.content if getattr(c, "text", None))
    return {"ok": True, "outil": outil, "args": args, "texte": texte}


async def lot(session: ClientSession, travaux_path: str, sortie_path: str) -> None:
    """Exécute les travaux un par un ; reprend là où le fichier de sortie s'est arrêté."""
    travaux = json.load(open(travaux_path, encoding="utf-8"))
    sortie = json.load(open(sortie_path, encoding="utf-8")) if os.path.exists(sortie_path) else {}
    for t in travaux:
        if sortie.get(t["id"], {}).get("ok"):
            continue
        sortie[t["id"]] = await appeler(session, t["outil"], t["args"])
        json.dump(sortie, open(sortie_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(t["id"], "ok" if sortie[t["id"]]["ok"] else "ERREUR", flush=True)
        await asyncio.sleep(random.uniform(*PAUSE_ENTRE_APPELS))


async def main(argv: List[str]) -> None:
    commande, args = commande_serveur()
    async with stdio_client(StdioServerParameters(command=commande, args=args, env=dict(os.environ))) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            if argv[0] == "outils":
                for t in (await session.list_tools()).tools:
                    print(t.name, "(lecture)" if outil_autorise(t.name) else "(écriture, refusé par ce client)")
            elif argv[0] == "appel":
                res = await appeler(session, argv[1], json.loads(argv[2]) if len(argv) > 2 else {})
                print(res.get("texte") or res.get("erreur"))
            elif argv[0] == "lot":
                await lot(session, argv[1], argv[2])
            else:
                sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1:]))
