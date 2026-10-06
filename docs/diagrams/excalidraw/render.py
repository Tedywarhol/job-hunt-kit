"""Rend un Canvas en PNG (échelle 2) et en fichier .excalidraw modifiable, avec Excalidraw lui-même.

Une page HTML (render.html) charge la bibliothèque @excalidraw/excalidraw depuis esm.sh, un Chrome sans
fenêtre (Playwright) convertit les éléments « squelette », puis exporte. Internet est nécessaire au rendu.
"""
import base64
import json
import os
import re
from typing import Any, Dict

from kit import Canvas

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.dirname(HERE)  # docs/diagrams/

JS = """async ({skeleton, files}) => {
  const X = window.X;
  const elements = X.convertToExcalidrawElements(skeleton);
  elements.forEach((el, i) => { el.seed = 1000 + i * 7919; });   // traits identiques d'un rendu à l'autre
  const appState = {exportBackground: true, viewBackgroundColor: "#ffffff"};
  const blob = await X.exportToBlob({elements, appState, files, mimeType: "image/png", exportPadding: 28,
    getDimensions: (w, h) => ({width: w * 2, height: h * 2, scale: 2})});
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = ""; for (const b of bytes) binary += String.fromCharCode(b);
  return {png: btoa(binary), elements};
}"""


def render_all(canvases: Dict[str, Canvas], png_dir: str = OUT_PNG) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("file:///" + os.path.join(HERE, "render.html").replace("\\", "/"))
        page.wait_for_function("window.__ready === true", timeout=180000)
        for filename, canvas in canvases.items():
            out: Dict[str, Any] = page.evaluate(JS, {"skeleton": canvas.skeleton(), "files": canvas.files()})
            with open(os.path.join(png_dir, f"{filename}.png"), "wb") as f:
                f.write(base64.b64decode(out["png"]))
            document = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": out["elements"],
                        "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": canvas.files()}
            with open(os.path.join(HERE, f"{filename}.excalidraw"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(document, f, ensure_ascii=False)
            print("rendu :", filename)
        browser.close()
