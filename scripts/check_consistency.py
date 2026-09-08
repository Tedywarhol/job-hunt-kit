#!/usr/bin/env python3
"""Contrôle de cohérence transactionnelle : outputs/ <-> state/outreach.json <-> Notion.

Brique M3 de docs/plans/2026-09-07-plan-amelioration.md — demandée explicitement par
l'audit du 2026-09-07 (« mécanisme de vérification systématique pour garantir qu'aucune
action ne casse la synchronisation des données »). Ne modifie JAMAIS rien : uniquement
un rapport, une ligne par catégorie (✅/⚠️/❌ comme le veut rules/10-audit-qualite-securite.mdc).

Vérifie :
  A. Dossiers outputs/<slug>/ avec CV+Lettre PDF prêts mais aucune trace « Postulé » (ou
     au-delà) dans Notion -> candidature préparée mais peut-être jamais envoyée.
  B. Entrées state/outreach.json (donc un email a déjà été drafté/envoyé à un recruteur)
     sans page Notion retrouvable -> Notion ne sait pas qu'on a contacté ce recruteur.
  C. Entrées state/outreach.json dont l'étape locale et le Statut Notion divergent de
     façon suspecte (ex. réponse reçue localement mais Notion encore sur "Postulé").
  D. Relances en retard (calcul local, sans appel réseau) — recoupe l'entonnoir Notion.

Usage:
  python scripts/check_consistency.py
"""
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from logutil import log_error
import push_notion as pn
from push_notion import norm_key  # ré-exporté : partagé avec find_similar_existing (N3)
from run_followups import DELAIS_JOURS, days_since, next_step

OUTREACH_PATH_DEFAULT: str = os.path.join(ROOT, "state", "outreach.json")
OUTPUTS_DIR_DEFAULT: str = os.path.join(ROOT, "outputs")

POSTULE_OU_APRES = {"Postulé", "Entretien", "Offre reçue", "Refusé", "Réponse reçue"}


def load_notion_index() -> Optional[Dict[str, Any]]:
    """Récupère toutes les pages Notion une seule fois, indexées par lien et par
    (entreprise, poste) normalisés. Renvoie None si Notion n'est pas configuré."""
    try:
        cfg = pn.load_cfg()
        db_id = pn.database_id_from_url(cfg["database_url"])
        token = pn.get_token()
        pages = pn.fetch_all_pages(token, db_id)
    except (SystemExit, FileNotFoundError):
        return None
    except Exception as e:
        log_error("check_consistency: requête Notion", e)
        return None

    by_url: Dict[str, Dict[str, Any]] = {}
    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for pg in pages:
        props = pg.get("properties", {})
        row = {
            "statut": pn.prop_select(props, "Statut"),
            "entreprise": pn.prop_text(props, "Entreprise"),
            "poste": pn.prop_text(props, "Poste"),
        }
        url = pn.prop_url(props, "Lien offre")
        if url:
            by_url[url] = row
        key = (norm_key(row["entreprise"]), norm_key(row["poste"]))
        by_key.setdefault(key, []).append(row)
    return {"by_url": by_url, "by_key": by_key, "total": len(pages)}


def find_notion_row(index: Dict[str, Any], lien: str, entreprise: str, poste: str) -> Optional[Dict[str, Any]]:
    if lien and lien in index["by_url"]:
        return index["by_url"][lien]
    matches = index["by_key"].get((norm_key(entreprise), norm_key(poste)), [])
    return matches[0] if len(matches) == 1 else None


def check_outputs_vs_notion(index: Optional[Dict[str, Any]], outputs_dir: Optional[str] = None) -> List[str]:
    warnings: List[str] = []
    for slug_dir in sorted(glob.glob(os.path.join(outputs_dir or OUTPUTS_DIR_DEFAULT, "*"))):
        slug = os.path.basename(slug_dir)
        if not os.path.isdir(slug_dir) or slug in ("archives", "previews", "radar"):
            continue
        lettre_vars = os.path.join(slug_dir, "lettre-vars.json")
        if not os.path.isfile(lettre_vars):
            continue
        pdfs = [f for f in os.listdir(slug_dir) if f.endswith(".pdf")]
        if not pdfs:
            continue
        try:
            with open(lettre_vars, "r", encoding="utf-8") as f:
                lv = json.load(f)
        except Exception as e:
            log_error(f"check_consistency: lecture {lettre_vars}", e)
            continue

        if index is None:
            continue
        # Ordre de confiance décroissant :
        # 1) le vrai lien de l'offre, quand lettre-vars.json le trace (M6, depuis le
        #    2026-09-07 — les dossiers créés avant n'en ont pas) ;
        # 2) le lien synthétique "https://job-hunt/<slug>" que certaines pages Notion
        #    créées manuellement portent en l'absence de lien connu (23 pages sur 206) ;
        # 3) en dernier recours, un match texte entreprise/poste — peu fiable, la
        #    formulation diffère souvent entre lettre-vars.json et Notion (ex. "AI Data
        #    Engineer / DataOps (Réf: ...)" vs "AI Data Engineer & DataOps (Patient &
        #    Clinical AI Teams)").
        row = None
        vrai_lien = lv.get("lien")
        if vrai_lien:
            row = index["by_url"].get(vrai_lien)
        if row is None:
            row = index["by_url"].get(f"https://job-hunt/{slug}")
        if row is None:
            row = find_notion_row(index, "", lv.get("entreprise", ""), lv.get("poste", ""))
        if row is None:
            warnings.append(
                f"outputs/{slug} : PDF prêts, aucune page Notion retrouvée avec confiance "
                f"(ni lien https://job-hunt/{slug}, ni texte entreprise/poste identique — "
                f"faux positif possible si le libellé Notion diffère juste en formulation)"
            )
        elif row["statut"] not in POSTULE_OU_APRES:
            warnings.append(f"outputs/{slug} : PDF prêts depuis un moment, Notion encore « {row['statut'] or '(vide)'} » — envoyée ou à laisser de côté ?")
    return warnings


def check_outreach_vs_notion(index: Optional[Dict[str, Any]], outreach_path: Optional[str] = None) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    path = outreach_path or OUTREACH_PATH_DEFAULT
    if not os.path.isfile(path):
        return errors, warnings
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        log_error(f"check_consistency: lecture {path}", e)
        errors.append(f"state/outreach.json illisible : {e!r}")
        return errors, warnings

    for entry in entries:
        entreprise, poste = entry.get("entreprise", ""), entry.get("poste", "")
        label = f"{entreprise} / {poste}"
        if index is None:
            continue
        row = find_notion_row(index, entry.get("lien", ""), entreprise, poste)
        if row is None:
            errors.append(f"outreach : {label} — email déjà contacté mais introuvable dans Notion (désync)")
            continue
        local_etape = entry.get("etape", "")
        if local_etape == "Réponse reçue" and row["statut"] not in ("Réponse reçue",):
            warnings.append(f"outreach : {label} — réponse reçue localement mais Notion dit « {row['statut'] or '(vide)'} »")
    return errors, warnings


def check_relances_dues(outreach_path: Optional[str] = None) -> List[str]:
    """Calcul purement local (pas d'appel réseau) : quelles candidatures ont dépassé
    leur échéance de relance ? Recoupe le même calcul que run_followups.py."""
    infos: List[str] = []
    path = outreach_path or OUTREACH_PATH_DEFAULT
    if not os.path.isfile(path):
        return infos
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        log_error(f"check_consistency: lecture {path}", e)
        return infos

    for entry in entries:
        etape = entry.get("etape", "J+0")
        if etape in ("Terminé", "Réponse reçue"):
            continue
        anchor = entry.get("date_j0") or entry.get("date_creation_brouillon")
        if not anchor:
            continue
        nxt = next_step(etape)
        if not nxt:
            continue
        elapsed = days_since(anchor)
        due = DELAIS_JOURS[nxt]
        if elapsed >= due:
            infos.append(f"{entry.get('entreprise', '?')} / {entry.get('poste', '?')} — {nxt} en retard de {elapsed - due} j")
    return infos


def main() -> None:
    print("\n" + "=" * 70)
    print("CONTRÔLE DE COHÉRENCE — outputs/ <-> state/outreach.json <-> Notion")
    print("=" * 70)

    index = load_notion_index()
    if index is None:
        print("\n⚠️  Notion non configuré ou injoignable — vérifications A/B/C limitées.")
    else:
        print(f"\n(Notion : {index['total']} page(s) chargée(s) pour comparaison)")

    out_warnings = check_outputs_vs_notion(index)
    outreach_errors, outreach_warnings = check_outreach_vs_notion(index)
    relances_dues = check_relances_dues()

    print("\nA. outputs/ vs Notion :")
    if not out_warnings:
        print("  ✅ Aucun dossier préparé sans trace Notion cohérente.")
    else:
        for w in out_warnings:
            print(f"  ⚠️  {w}")

    print("\nB/C. state/outreach.json vs Notion :")
    if not outreach_errors and not outreach_warnings:
        print("  ✅ Toutes les candidatures contactées sont synchronisées avec Notion.")
    else:
        for e in outreach_errors:
            print(f"  ❌ {e}")
        for w in outreach_warnings:
            print(f"  ⚠️  {w}")

    print("\nD. Relances en retard (calcul local) :")
    if not relances_dues:
        print("  ✅ Aucune relance en retard.")
    else:
        for r in relances_dues:
            print(f"  ⚠️  {r}")
        print("  -> python scripts/run_followups.py --apply")

    total_issues = len(out_warnings) + len(outreach_errors) + len(outreach_warnings) + len(relances_dues)
    print("\n" + "=" * 70)
    print(f"{'✅ Cohérence vérifiée, rien à signaler.' if total_issues == 0 else f'{total_issues} point(s) à vérifier ci-dessus.'}")
    print("=" * 70 + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
