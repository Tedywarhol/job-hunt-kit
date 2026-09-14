"""Tests de sécurité et de conformité pour le kit de partage."""
import os
import zipfile
from typing import Any, List

from make_kit import EXCLUDE_PATTERNS, SECRET_KEYWORDS, TEXT_EXTENSIONS, build_kit_zip, is_excluded

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_is_excluded_rules() -> None:
    # Fichiers et répertoires strictement exclus
    assert is_excluded(".git/config")
    assert is_excluded("outputs/offre-test/CV.pdf")
    assert is_excluded("state/seen.json")
    assert is_excluded("config/.notion_token")
    assert is_excluded("config/credentials.json")
    assert is_excluded("config/gmail_token.json")
    assert is_excluded("config/auth_url.txt")
    assert is_excluded(".claude/settings.local.json")
    assert is_excluded(".env")
    assert is_excluded("__pycache__/script.cpython-314.pyc")

    # Artefacts personnels/datés (2026-09-08) : jamais génériques, propres à ce déploiement.
    assert is_excluded("index.html")
    assert is_excluded("docs/plans/2026-09-07-analyse-existant.md")
    assert is_excluded("docs/plans/2026-09-07-plan-amelioration.md")
    assert is_excluded("config/apply-routine-schedule-prompt.md")
    assert is_excluded(".zcode/plans/plan-sess_abc.md")

    # Framework de règles personnel de l'utilisateur (2026-09-08) : sans rapport avec ce
    # projet Python (gstack, tracker "Propulse V2", défauts Next.js/Supabase).
    assert is_excluded(".claude/rules/00-dispatcher-skills.mdc")
    assert is_excluded(".claude/rules/01-skill-router.mdc")
    assert is_excluded(".claude/rules/20-ecriture-multiagents.mdc")
    assert is_excluded(".claude/rules/20-new-project.mdc")
    assert is_excluded(".claude/rules/30-new-feature.mdc")
    # Règles génériques : celles-là restent dans le kit.
    assert not is_excluded(".claude/rules/00-core.mdc")
    assert not is_excluded(".claude/rules/10-audit-qualite-securite.mdc")
    assert not is_excluded(".claude/rules/40-quality-gate.mdc")
    assert not is_excluded(".claude/rules/context7-docs.mdc")
    assert not is_excluded(".claude/rules/11-computer-use-files.mdc")
    # Recatégorisé le 2026-09-14 : contenu réel spécifique au Job-Hunt Kit malgré son nom,
    # pas le framework personnel (cf. CLAUDE.md § Conventions).
    assert not is_excluded(".claude/rules/10-session-start.mdc")

    # Fichiers autorisés dans le kit
    assert not is_excluded("scripts/init.py")
    assert not is_excluded("scripts/profile.py")
    assert not is_excluded("scripts/make_kit.py")
    assert not is_excluded("hunt.py")
    assert not is_excluded("templates/cv/cv.css")
    assert not is_excluded("templates/cv/cv-data.template.json")
    assert not is_excluded("README.md")
    assert not is_excluded("AGENTS.md")
    # Doc d'architecture générique (identité genericisée le 2026-09-08) : reste partagée.
    assert not is_excluded("docs/plans/2026-07-04-job-hunt-routine-design.md")


def _load_real_pii() -> List[str]:
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from profile import load_personal
    personal = load_personal()
    return [v.strip() for v in (personal.get("email"), personal.get("telephone")) if v and v.strip()]


def test_make_kit_source_has_no_hardcoded_pii() -> None:
    """make_kit.py doit charger l'email/téléphone dynamiquement (profile.load_personal),
    jamais les coder en dur — sinon le script lui-même diffuse ces données à chaque partage
    du kit, un bug réel corrigé le 2026-09-08."""
    src_path = os.path.join(ROOT, "scripts", "make_kit.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    for val in _load_real_pii():
        assert val not in src, f"make_kit.py contient encore '{val}' en dur"


def test_build_kit_zip_contains_no_real_pii(tmp_path: Any) -> None:
    """Bout en bout : construit un vrai kit et scanne TOUS les fichiers texte inclus
    (pas seulement cv-data.json) pour l'email/téléphone réel du profil actif."""
    pii_values = _load_real_pii()
    if not pii_values:
        return  # pas de profil réel configuré dans cet environnement de test

    out_zip = build_kit_zip(str(tmp_path / "kit-test.zip"))
    with zipfile.ZipFile(out_zip, "r") as z:
        for name in z.namelist():
            if os.path.splitext(name)[1].lower() not in TEXT_EXTENSIONS:
                continue
            try:
                content = z.read(name).decode("utf-8")
            except UnicodeDecodeError:
                continue
            for val in pii_values:
                assert val not in content, f"Donnée personnelle '{val}' résiduelle dans {name}"


def test_generated_kit_zip_integrity() -> None:
    # Vérifier le dernier zip généré si existant
    zips: List[str] = [f for f in os.listdir(ROOT) if f.startswith("job-hunt-kit_") and f.endswith(".zip")]
    if not zips:
        return

    latest_zip = os.path.join(ROOT, sorted(zips)[-1])
    with zipfile.ZipFile(latest_zip, "r") as z:
        names = z.namelist()
        for n in names:
            for kw in SECRET_KEYWORDS:
                assert kw not in n, f"Secret interdit dans le kit : {n}"
            assert not n.startswith("outputs/") or n.endswith(".gitkeep"), f"Dossier outputs/ non-vide présent : {n}"
            assert not n.startswith("state/") or n.endswith(".gitkeep"), f"Dossier state/ non-vide présent : {n}"

