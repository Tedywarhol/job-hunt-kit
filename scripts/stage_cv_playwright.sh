#!/usr/bin/env bash
# Copie un CV généré dans le conteneur Playwright (mcp/playwright) pour permettre
# l'upload via browser_file_upload (qui n'accepte que /home/node/*).
#
# Usage : bash scripts/stage_cv_playwright.sh "outputs/<slug>/CV_Prenom_NOM.pdf"
# Sort le chemin INTERNE à utiliser dans browser_file_upload (ex: /home/node/CV_Prenom_NOM.pdf).
#
# Pourquoi : le MCP Playwright tourne dans un conteneur Docker au FS isolé (aucun montage host).
# On y injecte le fichier avec `docker cp`. Racines autorisées par le MCP : /home/node, /home/node/.playwright-mcp.
set -euo pipefail
export MSYS_NO_PATHCONV=1

CV_SRC="${1:?chemin du CV requis}"
[ -f "$CV_SRC" ] || { echo "Fichier introuvable: $CV_SRC" >&2; exit 1; }

# Conteneur Playwright actif = celui qui exécute le chromium headless du MCP, le plus récent.
# (les conteneurs sont éphémères et renommés ; on cible par process, pas par nom/ancestor.)
CONTAINER=""
NEWEST=""
for c in $(docker ps --format '{{.Names}}'); do
  if docker top "$c" 2>/dev/null | grep -q 'cli.js --headless --browser chromium'; then
    created="$(docker inspect "$c" --format '{{.Created}}')"
    if [ -z "$NEWEST" ] || [ "$created" \> "$NEWEST" ]; then NEWEST="$created"; CONTAINER="$c"; fi
  fi
done
[ -n "$CONTAINER" ] || { echo "Aucun conteneur Playwright MCP (cli.js chromium) en cours." >&2; exit 1; }

BASENAME="$(basename "$CV_SRC")"
DEST="/home/node/${BASENAME}"
docker cp "$CV_SRC" "${CONTAINER}:${DEST}" >&2
echo "[stage_cv] $CV_SRC -> ${CONTAINER}:${DEST}" >&2
echo "$DEST"   # chemin interne pour browser_file_upload
