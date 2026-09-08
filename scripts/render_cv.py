#!/usr/bin/env python3
"""Génère le CV HTML puis PDF selon le Design System index.html (Navy #323B4C / Slate).
Intègre la Formation dans la Sidebar gauche, 3 Expériences + les 6 Projets d'envergure complets (avec puces structurées et bilans chiffrés),
et l'Option B pour les mots-clés ATS (couche blanche invisible + métadonnées PDF).

Usage:
  python scripts/render_cv.py --profile alternance \
      [--vars outputs/ENTREPRISE-POSTE/cv-vars.json] \
      [--out outputs/ENTREPRISE-POSTE/CV_NOM_Prenom_Alternance.html] [--pdf]
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

from typing import Any, Dict, List, Optional

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_DIR: str = os.path.join(ROOT, "templates", "cv")


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


def select_projets(projets: List[Dict[str, Any]], selection: List[str], projets_max: int = 6) -> List[Dict[str, Any]]:
    """Sélectionne et ordonne les projets selon la personnalisation."""
    if not selection:
        return projets[:projets_max]

    main_p: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = list(projets)
    for want in selection:
        for p in list(remaining):
            if want.lower() in p["titre"].lower():
                main_p.append(p)
                remaining.remove(p)
                break
    for p in remaining:
        if len(main_p) >= projets_max:
            break
        main_p.append(p)

    return main_p[:projets_max]


def build_sidebar_html(p: Dict[str, Any], badge_titre: str, prof: Dict[str, Any], competences: List[str], data: Dict[str, Any]) -> str:
    contact_html = f"""
        <div class="contact-item"><span class="ico">☎</span><a href="tel:{esc(p['telephone'])}">{esc(p['telephone'])}</a></div>
        <div class="contact-item"><span class="ico">✉</span><a href="mailto:{esc(p['email'])}">{esc(p['email'])}</a></div>
        <div class="contact-item"><span class="ico">⌂</span><span>{esc(p['localisation'])}</span></div>
        <div class="contact-item"><span class="ico">in</span><a href="{esc(p.get('linkedin_url', ''))}">{esc(p['linkedin'])}</a></div>
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
    langues_html = "".join(f'<div class="lang-item">{esc(l["langue"])} <span>— {esc(l["niveau"])}</span></div>' for l in data.get("langues", []))
    certifs_html = "".join(f'<div class="cert-item">{esc(c)}</div>' for c in data.get("certifications", []))
    interets_html = "".join(f"<span>{esc(it)}</span>" for it in data.get("interets", []))

    return f"""
    <aside class="sidebar">
        <div class="name">{esc(p['nom'])}</div>
        <div class="badge-title">{esc(badge_titre)}</div>
        <hr class="divider" />
        <div class="section-title">Contact</div>
        {contact_html}
        <div class="section-title">Formation</div>
        {formation_html}
        <div class="section-title">Compétences clés</div>
        <ul class="skill-list">{competences_li}</ul>
        <div class="section-title">Stack technique</div>
        {tech_groups_html}
        <div class="section-title">Savoir-être</div>
        <ul class="skill-list">{savoir_li}</ul>
        <div class="section-title">Langues</div>
        {langues_html}
        <div class="section-title">Certifications</div>
        {certifs_html}
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
            html_parts.append(f"""
            <div class="timeline-item">
                <div class="exp-header">
                    <span class="title">{esc(title_val)}</span>
                    <span class="company">{esc(item.get('entreprise', ''))} · {esc(item.get('lieu', ''))}</span>
                    <span class="date">{esc(item.get('periode', ''))}</span>
                </div>
                <ul class="exp-desc">{points_li}</ul>
            </div>""")
    return "".join(html_parts)


def build_html(data: Dict[str, Any], v: Dict[str, Any], profile: str) -> str:
    prof = data["profiles"][profile]
    p = data["personal"]
    titre_poste = v.get("titre") or prof.get("titre_defaut", "Alternance Data Science & IA")
    accroche = v.get("accroche") or data.get("profil_resume", "")
    badge_titre = v.get("badge_titre") or data.get("badge_titre", "Ingénieur Data & IA")

    competences = order_competences(data.get("competences_cles", []), v.get("competences_ordre", []))
    defaults = data.get("variables_defaut", {})
    selection = v.get("projets_selection", defaults.get("projets_selection", []))
    projets_max = v.get("projets_max", defaults.get("projets_max", len(data.get("projets", []))))
    main_projets = select_projets(data.get("projets", []), selection, projets_max)
    ats_keywords = v.get("mots_cles_ats", [])
    banner_tags = v.get("target_tags") or prof.get("target_tags", [])

    with open(os.path.join(CV_DIR, "cv.css"), "r", encoding="utf-8") as f:
        css = f.read()

    sidebar_html = build_sidebar_html(p, badge_titre, prof, competences, data)
    tags_html = "".join(f'<span class="target-tag">{esc(t["text"])}</span>' for t in banner_tags)
    exps_html = build_timeline_items_html(data.get("experiences", []), is_project=False)
    projets_html = build_timeline_items_html(main_projets, is_project=True)
    hidden_ats = f'<div class="ats-hidden-layer">{esc("ATS: " + ", ".join(ats_keywords))}</div>' if ats_keywords else ""

    return (
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>CV — {esc(p["nom"])}</title>'
        f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">'
        f'<style>{css}</style></head><body><div class="cv-page">{sidebar_html}<main class="main">'
        f'<div class="target-banner"><div class="target-title">{esc(titre_poste)}</div><div class="target-tags">{tags_html}</div></div>'
        f'<div class="section-title">Profil &amp; Adéquation</div><p class="profile-text">{esc(accroche)}</p>'
        f'<div class="section-title">Expériences professionnelles</div>{exps_html}'
        f'<div class="section-title">Projets d\'envergure</div>{projets_html}{hidden_ats}'
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


def to_pdf(html_path: str, pdf_path: str, title: str = "CV", keywords: Optional[List[str]] = None, author: str = "Candidat", subject: str = "Candidature") -> bool:
    chrome = find_chrome()
    if not chrome:
        print("[warn] Chrome/Edge introuvable — PDF non généré.", file=sys.stderr)
        return False
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    abs_pdf_path = os.path.abspath(pdf_path)
    import tempfile
    profile = tempfile.mkdtemp(prefix="cvchrome_")
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
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    if os.path.isfile(abs_pdf_path):
        inject_pdf_metadata(abs_pdf_path, title, keywords or [], author=author, subject=subject)
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["stage", "alternance"], required=True)
    ap.add_argument("--data", default=os.path.join(CV_DIR, "cv-data.json"))
    ap.add_argument("--vars", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    data = load_json(args.data)
    v = load_json(args.vars) if args.vars and os.path.isfile(args.vars) else {}
    
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from profile import doc_base_names
    p = data.get("personal", {})
    cv_base, _ = doc_base_names(p)
    out_html = args.out or os.path.join(ROOT, "outputs", f"{cv_base}_{args.profile.capitalize()}.html")
    os.makedirs(os.path.dirname(out_html), exist_ok=True)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(build_html(data, v, args.profile))
    print("HTML:", out_html)

    if args.pdf:
        pdf_path = os.path.splitext(out_html)[0] + ".pdf"
        title = v.get("titre") or f"CV {p.get('nom', 'Candidat')} - {args.profile.capitalize()}"
        keywords = v.get("mots_cles_ats", [])
        author = p.get("nom", "Candidat")
        subject = f"Candidature {p.get('nom', '')} - {args.profile.capitalize()}"
        if to_pdf(out_html, pdf_path, title=title, keywords=keywords, author=author, subject=subject):
            print("PDF:", pdf_path)


if __name__ == "__main__":
    main()
