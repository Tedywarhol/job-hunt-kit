"""Petit outil de dessin des schémas d'architecture du Job-Hunt Kit.

Chaque schéma est une page HTML autonome avec un SVG en ligne, dans l'esprit du plugin
diagram-design : connecteurs orthogonaux, étiquettes sur masque avec un écart de 8 px,
légende en bande basse, coordonnées sur une grille de 4 px, 9 blocs au plus.
Couleurs et police : bleu marine et Montserrat du design system des CV, accent orange.
"""
import html
from typing import Dict, List, Optional, Sequence, Tuple

PAPER, INK, MUTED, SOFT, ACCENT, LINK = "#f7f7f5", "#323b4c", "#4f5d75", "#7a8399", "#eb6c36", "#2e5aa8"
WIDTH, HEIGHT = 1280, 720
TOP = 48  # bande haute laissée vide : la zone visible commence à y = 48
Point = Tuple[int, int]

# fill, stroke, dash du cadre, couleur du texte de l'étiquette, nom dans la légende
KINDS: Dict[str, Dict[str, Optional[str]]] = {
    "focal": {"fill": "rgba(235,108,54,0.08)", "stroke": ACCENT, "dash": None, "tag": ACCENT, "legend": "Cœur du sujet"},
    "backend": {"fill": "#ffffff", "stroke": INK, "dash": None, "tag": INK, "legend": "Traitement"},
    "store": {"fill": "rgba(50,59,76,0.05)", "stroke": MUTED, "dash": None, "tag": MUTED, "legend": "Données locales"},
    "external": {"fill": "rgba(50,59,76,0.03)", "stroke": "rgba(50,59,76,0.30)", "dash": None, "tag": SOFT, "legend": "Service ou source externe"},
    "user": {"fill": "rgba(79,93,117,0.10)", "stroke": SOFT, "dash": None, "tag": SOFT, "legend": "Vous"},
    "security": {"fill": "rgba(235,108,54,0.05)", "stroke": "rgba(235,108,54,0.50)", "dash": "4,4", "tag": ACCENT, "legend": "Garde-fou"},
    "optional": {"fill": "rgba(50,59,76,0.02)", "stroke": "rgba(50,59,76,0.30)", "dash": "4,3", "tag": SOFT, "legend": "Automatique, en arrière-plan"},
}
EDGES = {
    "normal": {"stroke": MUTED, "width": 1.2, "dash": None, "marker": "arrow", "legend": "Flux"},
    "accent": {"stroke": ACCENT, "width": 1.4, "dash": None, "marker": "arrow-accent", "legend": "Flux principal"},
    "dashed": {"stroke": MUTED, "width": 1.0, "dash": "4,3", "marker": "arrow", "legend": "Retour ou mise à jour"},
}
CHAR_TITLE, CHAR_SUB, CHAR_LABEL = 7.0, 5.6, 5.4  # largeur moyenne d'un caractère (Montserrat 12, Geist Mono 9 et 8)


class Diagram:
    def __init__(self, slug: str, eyebrow: str, title: str, desc: str) -> None:
        self.slug, self.eyebrow, self.title, self.desc = slug, eyebrow, title, desc
        self.parts: List[str] = []   # nœuds, dessinés après les flèches
        self.arrows: List[str] = []
        self.labels: List[str] = []
        self.notes: List[str] = []
        self.kinds: List[str] = []
        self.styles: List[str] = []

    # --- blocs -------------------------------------------------------------------------------
    def node(self, x: int, y: int, w: int, h: int, kind: str, tag: str, title: str, subs: Sequence[str] = ()) -> None:
        assert all(v % 4 == 0 for v in (x, y, w, h)), f"{title} hors grille de 4 px"
        assert len(title) * CHAR_TITLE <= w - 24, f"titre trop long pour son bloc : {title}"
        for sub in subs:
            assert len(sub) * CHAR_SUB <= w - 24, f"sous-titre trop long pour son bloc : {sub}"
        style = KINDS[kind]
        dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
        tag_w = round(len(tag) * 5.8 + 12) // 4 * 4 + 4
        block = 12 + 14 * len(subs)
        title_y = y + (h - block) // 2 + 6 + 10
        out = [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>',
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="1"{dash}/>',
            f'<rect x="{x + 8}" y="{y + 6}" width="{tag_w}" height="12" rx="2" fill="transparent" stroke="{style["tag"]}" stroke-opacity="0.45" stroke-width="0.8"/>',
            f'<text x="{x + 8 + tag_w / 2}" y="{y + 15}" fill="{style["tag"]}" font-size="7" font-family="\'Geist Mono\', monospace" '
            f'text-anchor="middle" letter-spacing="0.08em">{html.escape(tag)}</text>',
            f'<text x="{x + w / 2}" y="{title_y}" fill="{INK}" font-size="12" font-weight="600" font-family="\'Montserrat\', sans-serif" '
            f'text-anchor="middle">{html.escape(title)}</text>',
        ]
        for i, sub in enumerate(subs):
            out.append(f'<text x="{x + w / 2}" y="{title_y + 16 + 14 * i}" fill="{MUTED}" font-size="9" '
                       f'font-family="\'Geist Mono\', monospace" text-anchor="middle">{html.escape(sub)}</text>')
        self.parts.append("\n        ".join(out))
        self.kinds.append(kind)

    # --- flèches -----------------------------------------------------------------------------
    def edge(self, points: Sequence[Point], style: str = "normal", label: str = "", at: Optional[Point] = None,
             side: str = "above") -> None:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            assert x1 == x2 or y1 == y2, f"segment diagonal interdit : {(x1, y1)} vers {(x2, y2)}"
        spec = EDGES[style]
        dash = f' stroke-dasharray="{spec["dash"]}"' if spec["dash"] else ""
        attrs = f'fill="none" stroke="{spec["stroke"]}" stroke-width="{spec["width"]}"{dash} marker-end="url(#{self.slug}-{spec["marker"]})"'
        self.arrows.append(f'<path d="{rounded_path(points)}" {attrs}/>')
        self.styles.append(style)
        if label:
            assert at is not None, f"position de l'étiquette manquante : {label}"
            self.labels.append(label_svg(label, at, side, ACCENT if style == "accent" else SOFT))

    def note(self, lines: Sequence[str], x: int, y: int, leader: str, dot: Point, anchor: str = "start") -> None:
        """Annotation en italique avec un trait pointillé qui désigne l'élément commenté."""
        text = "".join(
            f'<tspan x="{x}" dy="{0 if i == 0 else 20}">{html.escape(line)}</tspan>' for i, line in enumerate(lines))
        self.notes.append(
            f'<text x="{x}" y="{y}" fill="{INK}" font-size="14" font-style="italic" font-family="\'Instrument Serif\', serif" '
            f'text-anchor="{anchor}">{text}</text>\n        <path d="{leader}" fill="none" stroke="rgba(50,59,76,0.40)" '
            f'stroke-width="1" stroke-dasharray="4,3"/>\n        <circle cx="{dot[0]}" cy="{dot[1]}" r="2" fill="{INK}"/>')

    # --- sortie ------------------------------------------------------------------------------
    def legend(self) -> str:
        y = HEIGHT - 76
        out = [f'<line x1="40" y1="{y}" x2="{WIDTH - 40}" y2="{y}" stroke="rgba(50,59,76,0.10)" stroke-width="0.8"/>',
               f'<text x="40" y="{y + 20}" fill="{MUTED}" font-size="8" font-family="\'Geist Mono\', monospace" letter-spacing="0.18em">LÉGENDE</text>']
        x = 40
        for kind in dict.fromkeys(self.kinds):
            style = KINDS[kind]
            dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
            name = str(style["legend"])
            out.append(f'<rect x="{x}" y="{y + 32}" width="14" height="10" rx="2" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="1"{dash}/>')
            out.append(f'<text x="{x + 20}" y="{y + 40}" fill="{MUTED}" font-size="8.5" font-family="\'Montserrat\', sans-serif">{html.escape(name)}</text>')
            x += 20 + round(len(name) * 5.0) + 28
        for style_name in dict.fromkeys(self.styles):
            spec = EDGES[style_name]
            dash = f' stroke-dasharray="{spec["dash"]}"' if spec["dash"] else ""
            name = str(spec["legend"])
            out.append(f'<line x1="{x}" y1="{y + 37}" x2="{x + 28}" y2="{y + 37}" stroke="{spec["stroke"]}" stroke-width="{spec["width"]}"{dash} '
                       f'marker-end="url(#{self.slug}-{spec["marker"]})"/>')
            out.append(f'<text x="{x + 36}" y="{y + 40}" fill="{MUTED}" font-size="8.5" font-family="\'Montserrat\', sans-serif">{html.escape(name)}</text>')
            x += 36 + round(len(name) * 5.0) + 28
        assert x <= WIDTH - 20, f"légende trop large ({x})"
        return "\n        ".join(out)

    def svg(self) -> str:
        s = self.slug
        markers = "".join(
            f'<marker id="{s}-{name}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{color}"/></marker>\n          '
            for name, color in (("arrow", MUTED), ("arrow-accent", ACCENT)))
        body = "\n        ".join(self.arrows + self.labels + self.parts + self.notes)
        return (f'<svg viewBox="0 {TOP} {WIDTH} {HEIGHT - TOP}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{s}-title {s}-desc">\n'
                f'        <title id="{s}-title">{html.escape(self.title)}</title>\n'
                f'        <desc id="{s}-desc">{html.escape(self.desc)}</desc>\n'
                f'        <defs>\n          {markers}</defs>\n'
                f'        <rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>\n'
                f'        {body}\n        {self.legend()}\n      </svg>')

    def page(self) -> str:
        return PAGE.format(title=html.escape(self.title), eyebrow=html.escape(self.eyebrow), svg=self.svg())


def rounded_path(points: Sequence[Point], radius: int = 8) -> str:
    """Polyligne orthogonale dont chaque coude est un quart de cercle de rayon `radius`."""
    d = [f"M {points[0][0]},{points[0][1]}"]
    for i in range(1, len(points) - 1):
        (px, py), (cx, cy), (nx, ny) = points[i - 1], points[i], points[i + 1]
        sx, sy = _unit(px, py, cx, cy)
        ex, ey = _unit(cx, cy, nx, ny)
        d.append(f"L {cx - sx * radius},{cy - sy * radius} Q {cx},{cy} {cx + ex * radius},{cy + ey * radius}")
    d.append(f"L {points[-1][0]},{points[-1][1]}")
    return " ".join(d)


def _unit(x1: int, y1: int, x2: int, y2: int) -> Point:
    return ((x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1))


def label_svg(text: str, at: Point, side: str, color: str) -> str:
    """Étiquette de flèche sur un masque opaque, à 8 px du trait (jamais dessus)."""
    assert len(text) <= 14 and text == text.upper(), f"étiquette : 14 caractères majuscules au plus ({text})"
    w = round(len(text) * CHAR_LABEL + 10)
    x, y = at
    if side == "above":
        rx, ry, tx, ty, anchor = x - w / 2, y - 20, x, y - 11, "middle"
    elif side == "below":
        rx, ry, tx, ty, anchor = x - w / 2, y + 8, x, y + 17, "middle"
    elif side == "right":
        rx, ry, tx, ty, anchor = x + 8, y - 6, x + 13, y + 3, "start"
    else:
        rx, ry, tx, ty, anchor = x - 8 - w, y - 6, x - 13, y + 3, "end"
    return (f'<rect x="{rx}" y="{ry}" width="{w}" height="12" rx="2" fill="{PAPER}"/>'
            f'<text x="{tx}" y="{ty}" fill="{color}" font-size="8" font-family="\'Geist Mono\', monospace" '
            f'text-anchor="{anchor}" letter-spacing="0.06em">{html.escape(text)}</text>')


PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Montserrat:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    /* Skin : bleu marine et Montserrat du design system des CV (templates/cv/cv.css), accent orange. */
    :root {{ --paper: #f7f7f5; --ink: #323b4c; --muted: #4f5d75; }}
    body {{ font-family: 'Montserrat', 'Segoe UI', system-ui, sans-serif; background: var(--paper); color: var(--ink);
           min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1280px; width: 100%; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}
    .eyebrow {{ font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; font-weight: 500;
               letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem; }}
    h1 {{ font-family: 'Instrument Serif', 'Noto Serif', serif; font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem);
         font-weight: 400; letter-spacing: -0.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
    svg {{ width: 100%; min-width: 1280px; display: block; }}
    @media print {{ .diagram-container {{ overflow-x: visible; }} svg {{ min-width: 0; }} }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    <div class="diagram-container">
      {svg}
    </div>
  </div>
</body>
</html>
"""
