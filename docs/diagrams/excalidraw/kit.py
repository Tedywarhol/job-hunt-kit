"""Outils de dessin pour les schémas Excalidraw du Job-Hunt Kit.

Un `Canvas` rassemble des éléments « squelette » de l'API d'Excalidraw (`convertToExcalidrawElements`) :
zones, blocs avec logos de marque, flèches orthogonales, étiquettes, notes à la main et légende.
Le rendu (PNG et fichier .excalidraw modifiable) est fait par render.py.
"""
import base64
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
Point = Tuple[float, float]
FONT = 5                 # Excalifont, l'écriture à la main d'Excalidraw 0.18
INK, SOFT = "#1e1e1e", "#495057"
TITLE, SUB, LABEL = 22, 16, 17

# rôle : (remplissage, trait, nom dans la légende, trait pointillé)
ROLES: Dict[str, Tuple[str, str, str, bool]] = {
    "web": ("#d0ebff", "#1971c2", "Service en ligne", False),
    "python": ("#fff3bf", "#f08c00", "Traitement Python", False),
    "agent": ("#ffe8cc", "#e8590c", "Agent ou modèle IA", False),
    "data": ("#d3f9d8", "#2f9e44", "Données locales", False),
    "ui": ("#e5dbff", "#6741d9", "Interface", False),
    "guard": ("#ffe3e3", "#e03131", "Garde-fou", False),
    "you": ("#c5f6fa", "#0c8599", "Vous", False),
    "auto": ("#f1f3f5", "#868e96", "Automatique", True),
}

# nom : (fichier, couleur de marque, ou None si le fichier est déjà en couleurs)
LOGOS: Dict[str, Tuple[str, Optional[str]]] = {
    "linkedin": ("dv-linkedin.svg", None), "python": ("dv-python.svg", None), "chrome": ("dv-chrome.svg", None),
    "react": ("dv-react.svg", None), "typescript": ("dv-typescript.svg", None), "playwright": ("dv-playwright.svg", None),
    "notion": ("si-notion.svg", "#000000"), "gmail": ("si-gmail.svg", "#EA4335"), "claude": ("si-claude.svg", "#D97757"),
    "ollama": ("si-ollama.svg", "#000000"), "github": ("si-github.svg", "#181717"), "mcp": ("si-modelcontextprotocol.svg", "#1e1e1e"),
    "excalidraw": ("si-excalidraw.svg", "#6965DB"),
}


def logo_data_url(name: str) -> str:
    filename, color = LOGOS[name]
    with open(os.path.join(HERE, "logos", filename), encoding="utf-8") as f:
        svg = f.read()
    root = svg[svg.index("<svg"):svg.index(">", svg.index("<svg")) + 1]
    extra = ("" if "width=" in root else 'width="256" height="256" ') + (f'fill="{color}" ' if color else "")
    svg = svg.replace("<svg ", f"<svg {extra}", 1)  # les icônes Simple Icons sont monochromes : couleur de la marque
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def est(text: str, size: int) -> float:
    """Largeur approchée d'un texte en Excalifont."""
    return len(text) * size * 0.5


class Node:
    """Un bloc rectangulaire : repères pour accrocher les flèches."""

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h

    def top(self, dx: float = 0) -> Point:
        return (self.x + self.w / 2 + dx, self.y)

    def bottom(self, dx: float = 0) -> Point:
        return (self.x + self.w / 2 + dx, self.y + self.h)

    def left(self, dy: float = 0) -> Point:
        return (self.x, self.y + self.h / 2 + dy)

    def right(self, dy: float = 0) -> Point:
        return (self.x + self.w, self.y + self.h / 2 + dy)


class Canvas:
    def __init__(self, name: str, width: int, height: int, title: str, subtitle: str) -> None:
        self.name, self.width, self.height = name, width, height
        self.layers: Dict[str, List[Dict[str, Any]]] = {k: [] for k in ("zone", "arrow", "node", "text")}
        self.problems: List[str] = []
        self.logos: List[str] = []
        self.roles: List[str] = []
        self._n = 0
        self.text(40, 28, title, 34, INK)
        self.text(40, 76, subtitle, 20, SOFT)

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    # --- texte -------------------------------------------------------------------------------
    def text(self, x: float, y: float, text: str, size: int = SUB, color: str = INK, center: Optional[float] = None) -> str:
        """Texte à la main. Avec `center`, le texte est centré sur cette abscisse (Excalidraw centre le texte
        `textAlign: center` autour de son x)."""
        eid = self._id("t")
        element: Dict[str, Any] = {"type": "text", "id": eid, "x": x, "y": y, "text": text, "fontSize": size,
                                   "fontFamily": FONT, "strokeColor": color, "textAlign": "left"}
        if center is not None:
            element.update({"x": center, "textAlign": "center"})
        self.layers["text"].append(element)
        return eid

    # --- zones et blocs ------------------------------------------------------------------------
    def zone(self, x: float, y: float, w: float, h: float, title: str, color: str = "#868e96") -> None:
        self.layers["zone"].append({"type": "rectangle", "id": self._id("z"), "x": x, "y": y, "width": w, "height": h,
                                    "backgroundColor": "transparent", "strokeColor": color, "strokeStyle": "dashed",
                                    "strokeWidth": 2, "roughness": 1, "roundness": {"type": 3}})
        self.layers["text"].append({"type": "text", "id": self._id("t"), "x": x + 16, "y": y + 12, "text": title,
                                    "fontSize": 20, "fontFamily": FONT, "strokeColor": color})

    def node(self, x: float, y: float, w: float, role: str, title: str, subs: Sequence[str] = (),
             logos: Sequence[str] = (), h: Optional[float] = None) -> Node:
        fill, stroke, _legend, dashed = ROLES[role]
        for line in [title] + list(subs):
            size = TITLE if line == title else SUB
            if est(line, size) > w - 20:
                self.problems.append(f"texte trop large pour son bloc ({w}) : {line}")
        body = 30 + 21 * len(subs)                    # titre puis lignes de détail
        top = 74 if logos else 14                     # les logos occupent le haut du bloc
        height = h or top + body + 14
        if h and not logos:                           # bloc plus haut que son texte : on le centre
            top = max(14, (h - body) / 2)
        self.layers["node"].append({"type": "rectangle", "id": self._id("n"), "x": x, "y": y, "width": w, "height": height,
                                    "backgroundColor": fill, "fillStyle": "solid", "strokeColor": stroke, "strokeWidth": 2,
                                    "strokeStyle": "dashed" if dashed else "solid", "roughness": 1, "roundness": {"type": 3}})
        cx = x + w / 2
        badge, icon, gap = 52, 34, 12                 # pastille blanche et logo de la marque
        start = cx - (len(logos) * badge + (len(logos) - 1) * gap) / 2
        for i, name in enumerate(logos):
            if name not in self.logos:
                self.logos.append(name)
            bx = start + i * (badge + gap)
            self.layers["node"].append({"type": "rectangle", "id": self._id("p"), "x": bx, "y": y + 10, "width": badge, "height": badge,
                                        "backgroundColor": "#ffffff", "fillStyle": "solid", "strokeColor": "#ced4da",
                                        "strokeWidth": 1, "roughness": 1, "roundness": {"type": 3}})
            self.layers["node"].append({"type": "image", "id": self._id("i"), "x": bx + (badge - icon) / 2, "y": y + 10 + (badge - icon) / 2,
                                        "width": icon, "height": icon, "fileId": f"logo-{name}"})
        self.text(0, y + top, title, TITLE, INK, center=cx)
        for i, sub in enumerate(subs):
            self.text(0, y + top + 31 + 21 * i, sub, SUB, SOFT, center=cx)
        if role not in self.roles:
            self.roles.append(role)
        return Node(x, y, w, height)

    def badge(self, x: float, y: float, number: int) -> None:
        """Pastille numérotée posée sur le coin d'un bloc."""
        self.layers["text"].append({"type": "ellipse", "id": self._id("b"), "x": x, "y": y, "width": 38, "height": 38,
                                    "backgroundColor": INK, "fillStyle": "solid", "strokeColor": INK, "roughness": 1,
                                    "label": {"text": str(number), "fontSize": 22, "fontFamily": FONT, "strokeColor": "#ffffff"}})

    # --- flèches ---------------------------------------------------------------------------------
    def arrow(self, points: Sequence[Point], label: str = "", where: str = "above", dashed: bool = False,
              color: str = "#343a40", at: float = 0.5, segment: int = 0) -> None:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            assert x1 == x2 or y1 == y2, f"segment diagonal : {(x1, y1)} -> {(x2, y2)}"
        x0, y0 = points[0]
        self.layers["arrow"].append({"type": "arrow", "id": self._id("a"), "x": x0, "y": y0,
                                     "points": [[px - x0, py - y0] for px, py in points], "endArrowhead": "arrow",
                                     "startArrowhead": None, "strokeColor": color, "strokeWidth": 2, "roughness": 1,
                                     "roundness": None, "strokeStyle": "dashed" if dashed else "solid"})
        if label:
            (ax, ay), (bx, by) = points[segment], points[segment + 1]
            mx, my = ax + (bx - ax) * at, ay + (by - ay) * at
            width = est(label, LABEL)
            if where == "above":
                self.text(0, my - 30, label, LABEL, SOFT, center=mx)
            elif where == "below":
                self.text(0, my + 8, label, LABEL, SOFT, center=mx)
            elif where == "right":
                self.text(mx + 12, my - 11, label, LABEL, SOFT)
            else:  # left
                self.text(mx - 12 - width, my - 11, label, LABEL, SOFT)

    # --- légende et export ------------------------------------------------------------------------
    def legend(self, y: float) -> None:
        x = 40.0
        for role in self.roles:
            fill, stroke, name, dashed = ROLES[role]
            self.layers["text"].append({"type": "rectangle", "id": self._id("l"), "x": x, "y": y, "width": 26, "height": 18,
                                        "backgroundColor": fill, "fillStyle": "solid", "strokeColor": stroke,
                                        "strokeStyle": "dashed" if dashed else "solid", "roughness": 1, "roundness": {"type": 3}})
            self.text(x + 34, y - 2, name, 17, SOFT)
            x += 34 + est(name, 17) + 36

    def check(self) -> "Canvas":
        assert not self.problems, f"{self.name} : " + " | ".join(self.problems)
        return self

    def skeleton(self) -> List[Dict[str, Any]]:
        return [e for layer in ("zone", "arrow", "node", "text") for e in self.layers[layer]]

    def files(self) -> Dict[str, Dict[str, Any]]:
        return {f"logo-{n}": {"mimeType": "image/svg+xml", "id": f"logo-{n}", "dataURL": logo_data_url(n), "created": 1}
                for n in self.logos}
