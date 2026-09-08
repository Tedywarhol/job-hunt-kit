#!/usr/bin/env bash
# Lanceur 1-clic macOS & Linux pour le Job-Hunt Kit

set -e

if ! command -v python3 &> /dev/null; then
    echo "============================================================"
    echo "[ERREUR] Python 3 n'est pas installé."
    echo "Installez Python 3 via https://www.python.org/ ou votre gestionnaire de paquets (brew, apt)."
    echo "============================================================"
    exit 1
fi

python3 hunt.py "$@"
