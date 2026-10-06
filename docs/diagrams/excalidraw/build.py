#!/usr/bin/env python3
"""Régénère les schémas : PNG dans docs/diagrams/ et fichiers .excalidraw modifiables à côté de ce script.

  python docs/diagrams/excalidraw/build.py                # les six schémas
  python docs/diagrams/excalidraw/build.py radar pipeline  # certains seulement (mot contenu dans le nom)

Prérequis : `pip install playwright` puis `python -m playwright install chromium`, et un accès à Internet
(la bibliothèque Excalidraw et sa police sont chargées depuis esm.sh).
"""
import sys

from diagrams import build_all
from render import render_all

if __name__ == "__main__":
    wanted = sys.argv[1:]
    canvases = {name: canvas for name, canvas in build_all().items() if not wanted or any(w in name for w in wanted)}
    render_all(canvases)
