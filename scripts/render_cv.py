#!/usr/bin/env python3
"""Génère le CV HTML puis PDF selon le Design System index.html (Navy #323B4C / Slate).
Intègre la Formation dans la Sidebar gauche, 3 Expériences + les Projets d'envergure retenus (avec puces structurées et bilans chiffrés),
et l'Option B pour les mots-clés ATS (couche blanche invisible + métadonnées PDF).

Garde-fou de tenue (2026-10-03) : avec `--pdf`, le CV doit tenir sur UNE page A4 avec au moins
MARGE_BAS_MIN_MM de blanc sous le dernier élément de la colonne blanche. Sinon les derniers
projets de la sélection sont retirés un à un jusqu'à ce que ça tienne (`--no-autofit` pour
l'interdire). Si même PROJETS_MIN projets ne tiennent pas, code de sortie 3.

Usage:
  python scripts/render_cv.py --profile alternance \
      [--vars outputs/ENTREPRISE-POSTE/cv-vars.json] \
      [--out outputs/ENTREPRISE-POSTE/CV_NOM_Prenom_Alternance.html] [--pdf] [--no-autofit]
"""
import argparse
import re
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

from typing import Any, Callable, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_DIR: str = os.path.join(ROOT, "templates", "cv")

# Le gabarit coupe en silence tout ce qui dépasse de la page (`.cv-page { overflow: hidden }`) :
# un CV trop chargé reste « une page » en perdant ses dernières puces. Constat du 2026-10-03 : le CV
# maître avait son dernier projet coupé à 0,3 mm du bord, et une quarantaine de CV générés
# avaient moins de 6 mm de blanc. D'où cette règle, vérifiée à chaque génération de PDF.
MARGE_BAS_MIN_MM: float = 12.0
PROJETS_MIN: int = 2  # en dessous, ce n'est plus le nombre de projets qui est en cause : code de sortie 3
EXIT_TROP_CHARGE: int = 3


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_chrome() -> Optional[str]:
    """Détecte Chrome/Edge/Chromium sur Windows, macOS et Linux.

    Corrigé le 2026-09-08 : ne couvrait que des chemins Windows en dur — sur une machine
    macOS/Linux fraîche (le projet annonce pourtant `hunt.sh` pour ces plateformes), rien
    n'était trouvé sans que l'utilisateur sache qu'il fallait déjà connaître la variable
    d'environnement CHROME_PATH documentée en dépannage.
    """
    candidates: List[Optional[str]] = [os.environ.get("CHROME_PATH")]

    if sys.platform.startswith("win"):
        candidates += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux et assimilés
        candidates += [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
            "/snap/bin/chromium",
        ]

    # PATH : couvre les noms de binaire les plus courants sur chaque OS.
    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                "chrome", "chrome.exe", "microsoft-edge", "msedge"):
        candidates.append(shutil.which(exe))

    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def order_competences(base: List[str], order: List[str]) -> List[str]:
    """Remonte en tête les compétences correspondant aux mots-clés de l'offre."""
    if not order:
        return list(base)
    ranked: List[str] = []
    rest: List[str] = list(base)
    for key in order:
        for c in list(rest):
            if key.lower() in c.lower():
                ranked.append(c)
                rest.remove(c)
    return ranked + rest


def retirer_tirets_cadratins(texte: str) -> str:
    """Aucun « — » dans un CV (règle du projet, rappelée le 2026-10-03) : « A — B » devient « A : B »."""
    return re.sub(r"\s*—\s*", " : ", texte)


def badge_etudiant(badge: str) -> str:
    """Un étudiant n'est pas encore ingénieur (retour du 2026-10-03) : « Ingénieur Data & IA » devient
    « Étudiant ingénieur » puis « Data & IA » sur la ligne suivante. Les autres titres restent tels quels."""
    m = re.match(r"^\s*ing[ée]nieure?\b[\s&·,\-]*(.*)$", badge, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return badge
    reste = m.group(1).strip()
    return "Étudiant ingénieur" + (f"\n{reste}" if reste else "")


def _clef_titre(titre: str) -> str:
    """Titre comparable : les anciens cv-vars écrivent « A — B », les titres du CV maître « A : B »."""
    return re.sub(r"\s+", " ", retirer_tirets_cadratins(titre)).strip().lower()


def select_projets(projets: List[Dict[str, Any]], selection: List[str], projets_max: int = 6) -> List[Dict[str, Any]]:
    """Sélectionne et ordonne les projets selon la personnalisation."""
    if not selection:
        return projets[:projets_max]

    main_p: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = list(projets)
    for want in selection:
        for p in list(remaining):
            if _clef_titre(want) in _clef_titre(p["titre"]):
                main_p.append(p)
                remaining.remove(p)
                break
    for p in remaining:
        if len(main_p) >= projets_max:
            break
        main_p.append(p)

    return main_p[:projets_max]


def projets_retenus(data: Dict[str, Any], v: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Projets affichés pour ces variables : la sélection de l'offre, sinon celle du CV maître."""
    defaults = data.get("variables_defaut", {})
    selection = v.get("projets_selection", defaults.get("projets_selection", []))
    projets_max = v.get("projets_max", defaults.get("projets_max", len(data.get("projets", []))))
    return select_projets(data.get("projets", []), selection, projets_max)


def tel_href(tel: str) -> str:
    """Numéro au format tel: valide (sans espaces, indicatif +33 pour un numéro français en 0X)."""
    digits = re.sub(r"[^\d+]", "", tel)
    if re.fullmatch(r"0\d{9}", digits):
        digits = "+33" + digits[1:]
    return "tel:" + digits


def build_sidebar_html(p: Dict[str, Any], badge_titre: str, prof: Dict[str, Any], competences: List[str], data: Dict[str, Any]) -> str:
    formation_main = bool(data.get("style", {}).get("formation_main"))
    linkedin_html = (
        f'<div class="contact-item"><span class="ico">in</span><a href="{esc(p.get("linkedin_url", ""))}">{esc(p["linkedin"])}</a></div>'
        if p.get("linkedin") else ""
    )
    contact_html = f"""
        <div class="contact-item"><span class="ico">☎</span><a href="{esc(tel_href(p['telephone']))}">{esc(p['telephone'])}</a></div>
        <div class="contact-item"><span class="ico">✉</span><a href="mailto:{esc(p['email'])}">{esc(p['email'])}</a></div>
        <div class="contact-item"><span class="ico">⌂</span><span>{esc(p['localisation'])}</span></div>
        {linkedin_html}
    """
    formation_html = "".join(
        f"""<div class="edu-side-item">
            <div class="edu-side-school">{esc(fo['etablissement'])}</div>
            <div class="edu-side-degree">{esc(fo['intitule'])}</div>
            <div class="edu-side-meta"><span>{esc(fo['lieu'])}</span><span>{esc(fo['periode'])}</span></div>
        </div>""" for fo in prof.get("formation", [])
    )
    competences_li = "".join(f"<li>{esc(c)}</li>" for c in competences)
    tech_groups_html = "".join(
        f'<div class="tech-group"><span class="label">{esc(k)}</span><span class="value">{esc(", ".join(val))}</span></div>'
        for k, val in data.get("outils", {}).items()
    )
    savoir_li = "".join(f"<li>{esc(s)}</li>" for s in data.get("savoir_etre", []))
    langues_html = "".join(f'<div class="lang-item">{esc(l["langue"])} <span>· {esc(l["niveau"])}</span></div>' for l in data.get("langues", []))
    certifs_html = "".join(f'<div class="cert-item">{esc(c)}</div>' for c in data.get("certifications", []))
    interets_html = "".join(f"<span>{esc(it)}</span>" for it in data.get("interets", []))

    return f"""
    <aside class="sidebar">
        <div class="name">{esc(p['nom'])}</div>
        <div class="badge-title">{esc(badge_titre).replace(chr(10), "<br>")}</div>
        <hr class="divider" />
        <div class="section-title">Contact</div>
        {contact_html}
        {'' if formation_main else '<div class="section-title">Formation</div>' + formation_html}
        <div class="section-title">Compétences clés</div>
        <ul class="skill-list">{competences_li}</ul>
        <div class="section-title">Stack technique</div>
        {tech_groups_html}
        {'<div class="section-title">Savoir-être</div><ul class="skill-list">' + savoir_li + '</ul>' if savoir_li else ""}
        <div class="section-title">Langues</div>
        {langues_html}
        {'<div class="section-title">Certifications</div>' + certifs_html if certifs_html else ""}
        <div class="section-title">Intérêts</div>
        <div class="interests">{interets_html}</div>
    </aside>"""


def build_timeline_items_html(items: List[Dict[str, Any]], is_project: bool = False) -> str:
    html_parts: List[str] = []
    for item in items:
        points_li = "".join(
            f'<span class="bilan">{esc(pt)}</span>' if pt.startswith("✓") else f'<li>{esc(pt)}</li>'
            for pt in item.get("points", [])
        )
        if is_project:
            stack_html = f'<span class="project-stack">{esc(item.get("stack", ""))}</span>' if item.get("stack") else ""
            html_parts.append(f"""
            <div class="project-item">
                <div class="project-header"><span class="project-title">{esc(item['titre'])}</span>{stack_html}</div>
                <ul class="project-desc">{points_li}</ul>
            </div>""")
        else:
            title_val = item.get("intitule") or item.get("titre", "")
            # Le type de contrat (Stage, Alternance...) s'affiche en tête de la ligne entreprise : un stage ne doit
            # jamais passer pour un poste (retour du 2026-10-03, « ça ne se voit absolument nulle part »).
            contrat_html = f'<strong class="contrat">{esc(item["contrat"])}</strong> · ' if item.get("contrat") else ""
            html_parts.append(f"""
            <div class="timeline-item">
                <div class="exp-header">
                    <span class="title">{esc(title_val)}</span>
                    <span class="company">{contrat_html}{esc(item.get('entreprise', ''))} · {esc(item.get('lieu', ''))}</span>
                    <span class="date">{esc(item.get('periode', ''))}</span>
                </div>
                <ul class="exp-desc">{points_li}</ul>
            </div>""")
    return "".join(html_parts)


def scale_css(css: str, font_scale: float, line_scale: float) -> str:
    """Agrandit les tailles de police et interlignes du CSS (opt-in via data["style"])."""
    css = re.sub(r"font-size:\s*([\d.]+)px", lambda m: f"font-size: {float(m.group(1)) * font_scale:.2f}px", css)
    return re.sub(r"line-height:\s*([\d.]+)(?![\d.]*px)", lambda m: f"line-height: {float(m.group(1)) * line_scale:.3f}", css)


def build_formation_main_html(formations: List[Dict[str, Any]]) -> str:
    items = [
        {"intitule": fo["intitule"], "entreprise": fo.get("etablissement", ""), "lieu": fo.get("lieu", ""),
         "periode": fo.get("periode", ""), "points": [fo["detail"]] if fo.get("detail") else []}
        for fo in formations
    ]
    return build_timeline_items_html(items, is_project=False)


def build_projets_html(projets: List[Dict[str, Any]]) -> str:
    """Un seul bloc « Projets d'envergure », ou un bloc par `categorie` si les projets en portent."""
    if not any(pr.get("categorie") for pr in projets):
        return f'<div class="section-title">Projets d&#x27;envergure</div>{build_timeline_items_html(projets, is_project=True)}'
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for pr in projets:
        groups.setdefault(pr.get("categorie", "Projets"), []).append(pr)
    return "".join(
        f'<div class="section-title">{esc(cat)}</div>{build_timeline_items_html(items, is_project=True)}'
        for cat, items in groups.items()
    )


def build_html(data: Dict[str, Any], v: Dict[str, Any], profile: str) -> str:
    prof = data["profiles"][profile]
    p = data["personal"]
    titre_poste = v.get("titre") or prof.get("titre_defaut", "Alternance Data Science & IA")
    accroche = v.get("accroche") or data.get("profil_resume", "")
    badge_titre = badge_etudiant(v.get("badge_titre") or data.get("badge_titre", "Étudiant ingénieur\nData Science & IA"))

    competences = order_competences(data.get("competences_cles", []), v.get("competences_ordre", []))
    main_projets = projets_retenus(data, v)
    ats_keywords = v.get("mots_cles_ats", [])
    banner_tags = v.get("target_tags") or prof.get("target_tags", [])

    with open(os.path.join(CV_DIR, "cv.css"), "r", encoding="utf-8") as f:
        css = f.read()
    style = data.get("style", {})
    css += "\n.formation-block .timeline-item + .timeline-item { margin-top: 14px; }\n"
    if style.get("font_scale") or style.get("line_height_scale"):
        css = scale_css(css, style.get("font_scale", 1.0), style.get("line_height_scale", 1.0))

    sidebar_html = build_sidebar_html(p, badge_titre, prof, competences, data)
    tags_html = "".join(f'<span class="target-tag">{esc(t["text"])}</span>' for t in banner_tags)
    exps_html = build_timeline_items_html(data.get("experiences", []), is_project=False)
    projets_html = build_projets_html(main_projets)
    formation_first = style.get("formation_position", "start") != "end"
    formation_html = (
        f'<div class="section-title">Formation</div><div class="formation-block">{build_formation_main_html(prof.get("formation", []))}</div>'
        if style.get("formation_main") else ""
    )
    hidden_ats = f'<div class="ats-hidden-layer">{esc("ATS: " + ", ".join(ats_keywords))}</div>' if ats_keywords else ""

    return retirer_tirets_cadratins(
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>CV {esc(p["nom"])}</title>'
        f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">'
        f'<style>{css}</style></head><body><div class="cv-page">{sidebar_html}<main class="main">'
        f'<div class="target-banner"><div class="target-title">{esc(titre_poste)}</div><div class="target-tags">{tags_html}</div></div>'
        f'<div class="section-title">Profil &amp; Adéquation</div><p class="profile-text">{esc(accroche)}</p>'
        f'{formation_html if formation_first else ""}'
        f'<div class="section-title">Expériences professionnelles</div>{exps_html}'
        f'{projets_html}'
        f'{"" if formation_first else formation_html}{hidden_ats}'
        f'</main></div></body></html>'
    )


def inject_pdf_metadata(pdf_path: str, title: str, keywords_list: List[str], author: str = "Candidat", subject: str = "Candidature") -> None:
    """Injecte les métadonnées de titre et mots-clés ATS dans le fichier PDF (Option B)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        metadata = {
            "/Title": title,
            "/Author": author,
            "/Subject": subject,
            "/Keywords": ", ".join(keywords_list) if keywords_list else "Data Science, IA, GenAI, Python, LLM, Machine Learning",
            "/Creator": "Job-Hunt Kit Automated Pipeline",
        }
        writer.add_metadata(metadata)
        with open(pdf_path, "wb") as f_out:
            writer.write(f_out)
    except Exception as e:
        print(f"[note] Metadata injection: {e}", file=sys.stderr)


def _imprimer_pdf(chrome: str, html_path: str, abs_pdf_path: str) -> None:
    """Imprime `html_path` en PDF avec Chrome/Edge headless (profil jetable, format de la règle @page)."""
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    profile = tempfile.mkdtemp(prefix="cvchrome_")
    try:
        try:
            subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-pdf-header-footer",
                    f"--user-data-dir={profile}",
                    f"--print-to-pdf={abs_pdf_path}",
                    url,
                ],
                check=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            # Chrome headless écrit parfois le PDF sur disque avant de terminer
            # proprement son propre process (observé sous charge, plusieurs instances
            # concurrentes) : le sous-processus Python dépasse alors les 120s bien que
            # le fichier soit déjà complet. On ne traite ça comme un échec réel que si
            # le fichier est absent.
            if not os.path.isfile(abs_pdf_path):
                raise
            print(f"[note] Chrome a dépassé le timeout de 120s mais {os.path.basename(abs_pdf_path)} a bien été écrit — poursuite.", file=sys.stderr)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def to_pdf(html_path: str, pdf_path: str, title: str = "CV", keywords: Optional[List[str]] = None, author: str = "Candidat", subject: str = "Candidature") -> bool:
    chrome = find_chrome()
    if not chrome:
        print("[warn] Chrome/Edge introuvable — PDF non généré.", file=sys.stderr)
        return False
    abs_pdf_path = os.path.abspath(pdf_path)
    _imprimer_pdf(chrome, html_path, abs_pdf_path)

    if os.path.isfile(abs_pdf_path):
        inject_pdf_metadata(abs_pdf_path, title, keywords or [], author=author, subject=subject)
        return True
    return False


def css_controle_tenue(marge_mm: float) -> str:
    """Surcharge CSS (insérée avant </head>) qui autorise le dépassement et réserve `marge_mm` en bas.

    Variante jetable du CV : plus de hauteur fixe ni de `overflow: hidden`, et le padding bas de la
    colonne blanche vaut la marge exigée. Si contenu + marge dépassent 297 mm, Chrome ouvre une seconde page.
    """
    return (
        '<style id="controle-tenue">'
        ".cv-page{height:auto !important;min-height:297mm !important;max-height:none !important;overflow:visible !important}"
        ".sidebar,.main{height:auto !important;overflow:visible !important}"
        f".main{{padding-bottom:{marge_mm:.2f}mm !important}}"
        "</style></head>"
    )


def tient_sur_une_page(html_path: str, marge_mm: float = MARGE_BAS_MIN_MM) -> Optional[bool]:
    """Vrai si le CV tient sur UNE page A4 avec au moins `marge_mm` de blanc sous son dernier élément.

    Compter les pages du vrai PDF ne détecte rien (le gabarit coupe ce qui dépasse) : on imprime donc
    la variante de `css_controle_tenue` et on compte ses pages. Mesuré le 2026-10-03 sur cinq CV de
    marges connues (0,3 / 1,8 / 5,1 / 29 / 66 mm) : le verdict concorde à chaque fois avec la mesure
    au pixel. Renvoie None quand le contrôle est impossible (Chrome introuvable, impression en échec).
    """
    chrome = find_chrome()
    if not chrome:
        return None
    tmp = tempfile.mkdtemp(prefix="cvfit_")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            source = f.read()
        if "</head>" not in source:
            return None
        variante = os.path.join(tmp, "variante.html")
        with open(variante, "w", encoding="utf-8") as f:
            f.write(source.replace("</head>", css_controle_tenue(marge_mm), 1))
        pdf = os.path.join(tmp, "variante.pdf")
        _imprimer_pdf(chrome, variante, pdf)
        if not os.path.isfile(pdf):
            return None
        import pypdf
        return len(pypdf.PdfReader(pdf).pages) == 1
    except Exception as e:  # le contrôle est best-effort : un échec n'est jamais pris pour un « ça tient »
        from logutil import log_error
        log_error("Contrôle de tenue du CV impossible", e)
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ajuster_projets(essayer: Callable[[int], bool], n_depart: int, n_min: int = PROJETS_MIN) -> Optional[int]:
    """Plus grand n de [n_min, n_depart] pour lequel `essayer(n)` est vrai, en partant de n_depart.

    On retire un projet à la fois : c'est toujours le dernier de la sélection (le moins prioritaire)
    qui saute en premier. None si aucun n ne convient.
    """
    for n in range(n_depart, n_min - 1, -1):
        if essayer(n):
            return n
    return None


def ajuster_html(data: Dict[str, Any], v: Dict[str, Any], profile: str, out_html: str,
                 autofit: bool = True, marge_mm: float = MARGE_BAS_MIN_MM) -> Dict[str, Any]:
    """Écrit le HTML du CV en visant « une page A4 avec `marge_mm` de blanc en bas ».

    Avec `autofit`, retire les derniers projets tant que ça ne tient pas. Le fichier écrit correspond
    toujours au dernier essai. Retour : n_depart, n (projets gardés), retires (titres), tient
    (True, False, ou None quand le contrôle n'a pas pu être fait).
    """
    titres = [p["titre"] for p in projets_retenus(data, v)]
    n_depart = len(titres)
    dernier = n_depart

    def ecrire(n: int) -> None:
        nonlocal dernier
        dernier = n
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(build_html(data, {**v, "projets_max": n}, profile))

    ecrire(n_depart)
    tient = tient_sur_une_page(out_html, marge_mm)
    if tient is False and autofit:
        def essayer(n: int) -> bool:
            ecrire(n)
            return bool(tient_sur_une_page(out_html, marge_mm))
        tient = ajuster_projets(essayer, n_depart - 1, min(PROJETS_MIN, n_depart)) is not None
    return {"n_depart": n_depart, "n": dernier, "retires": titres[dernier:], "tient": tient}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["stage", "alternance"], required=True)
    ap.add_argument("--data", default=os.path.join(CV_DIR, "cv-data.json"))
    ap.add_argument("--vars", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--no-autofit", action="store_true",
                    help=f"ne retire aucun projet : signale seulement un CV qui ne tient pas avec {MARGE_BAS_MIN_MM:.0f} mm de blanc en bas")
    args = ap.parse_args()

    data = load_json(args.data)
    v = load_json(args.vars) if args.vars and os.path.isfile(args.vars) else {}

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from profile import doc_base_names
    p = data.get("personal", {})
    cv_base, _ = doc_base_names(p)
    out_html = args.out or os.path.join(ROOT, "outputs", f"{cv_base}_{args.profile.capitalize()}.html")
    os.makedirs(os.path.dirname(out_html), exist_ok=True)

    if not args.pdf:  # aperçu HTML seul : rapide, sans contrôle de tenue
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(build_html(data, v, args.profile))
        print("HTML:", out_html)
        return

    bilan = ajuster_html(data, v, args.profile, out_html, autofit=not args.no_autofit)
    print("HTML:", out_html)
    pdf_path = os.path.splitext(out_html)[0] + ".pdf"
    title = v.get("titre") or f"CV {p.get('nom', 'Candidat')} - {args.profile.capitalize()}"
    keywords = v.get("mots_cles_ats", [])
    author = p.get("nom", "Candidat")
    subject = f"Candidature {p.get('nom', '')} - {args.profile.capitalize()}"
    if to_pdf(out_html, pdf_path, title=title, keywords=keywords, author=author, subject=subject):
        print("PDF:", pdf_path)

    if bilan["tient"] is None:
        print("[warn] Tenue du CV non vérifiée (Chrome/Edge introuvable ou impression en échec) : "
              "ouvre le PDF et vérifie qu'il y a du blanc sous la dernière ligne.", file=sys.stderr)
    elif bilan["tient"] is False:
        print(f"[ERREUR] Le CV ne tient pas sur une page A4 avec {MARGE_BAS_MIN_MM:.0f} mm de blanc en bas "
              f"({bilan['n']} projet(s) sur {bilan['n_depart']}). "
              + ("Raccourcis l'accroche ou les puces des expériences." if not args.no_autofit
                 else "Relance sans --no-autofit pour retirer les derniers projets, ou raccourcis le contenu."),
              file=sys.stderr)
        sys.exit(EXIT_TROP_CHARGE)
    elif bilan["retires"]:
        print(f"[ajusté] {bilan['n']} projet(s) sur {bilan['n_depart']} pour garder {MARGE_BAS_MIN_MM:.0f} mm de blanc en bas ; "
              f"retiré(s) : {' ; '.join(bilan['retires'])}.")


if __name__ == "__main__":
    main()
