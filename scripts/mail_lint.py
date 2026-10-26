#!/usr/bin/env python3
"""Contrôles de langue pour les mails de prospection.

Retour du 2026-10-12 : les mails partis ce jour-là avaient « encore des coquilles » et ne sonnaient pas assez
naturels. Un correcteur orthographique ne voyait rien (aucun mot mal écrit) : les défauts étaient d'un autre ordre,
et se répétaient d'un mail à l'autre. Ces contrôles les attrapent :
  - un adjectif rattaché au mauvais mot (« une alternance de 24 mois, disponible immédiatement ») ;
  - les mêmes phrases recopiées d'un mail à l'autre d'un même lot ;
  - les tics de rédaction (« je me permets » partout, « bien plus qu'un… : c'est… », « dès le premier jour ») ;
  - un pronom ambigu (« son message m'a orienté vers vous ») ;
  - la typographie (espaces doubles, apostrophes mélangées, « coeur » sans ligature).
Signalements pour relecture, jamais bloquants. L'orthographe lexicale est facultative : elle utilise
`pyspellchecker` s'il est installé (`pip install pyspellchecker`), sinon elle est ignorée.
"""
import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

# Un mail ne supporte qu'un petit nombre de ces tournures : au-delà, le texte sonne en pilote automatique.
LIMITES_OCCURRENCES: Dict[str, int] = {
    "je me permets": 1,
    "sincèrement": 1,
    "passion": 1,
    "à votre disposition": 1,
    "vraiment": 2,
}

TOURNURES_A_EVITER: List[Tuple[str, str]] = [
    ("bien plus qu'un", "parallélisme « pas seulement X, mais Y » : dire directement la chose"),
    ("ce n'est pas seulement", "parallélisme « pas seulement X, mais Y » : dire directement la chose"),
    ("dès le premier jour", "promesse creuse : donner un fait à la place"),
    ("mon énergie et mon sérieux", "autoéloge sans preuve : donner un fait à la place"),
    ("à votre entière disposition", "formule d'usage creuse"),
    ("son message m'a", "pronom ambigu : nommer la personne"),
    ("sa réponse m'a", "pronom ambigu : nommer la personne"),
]

LIGATURES_OUBLIEES: List[str] = ["coeur", "oeuvre", "soeur", "boeuf", "oeil"]

# Nombre de mots en deçà duquel une phrase ne compte pas pour la comparaison d'un lot (« Mon CV est joint. »).
MIN_MOTS_PHRASE = 9

# La signature et la formule de fin ouvrent la partie ignorée par la comparaison d'un lot.
FORMULE_DE_FIN = re.compile(r"\n\s*(?:Bien cordialement|Cordialement|Bien à vous|Bonne journée à vous)\b", re.IGNORECASE)

# Anglicismes et mots courants du métier que le dictionnaire français ne connaît pas.
MOTS_AUTORISES = {
    "visio", "dashboards", "dashboard", "scraping", "analyst", "learning", "web", "retail", "data", "cloud",
    "workflow", "workflows", "scientists", "scientist", "engineer", "llm", "rag", "devops", "cv", "ia",
}

MODIFIEUR_MAL_RATTACHE = re.compile(r"alternance[^.\n]{0,100}?,\s*(?:disponible|prêt|motivé)", re.IGNORECASE)

# Typographie française (règle du 2026-10-14) : espace insécable avant « : ; ? ! » et dans les guillemets « ».
# Les heures (14:00) et les liens ne comptent pas : le signe doit être suivi d'un blanc ou de la fin du texte.
NBSP = "\xa0"
_LIEN = re.compile(r"\S*(?:@|://)\S*")
_PONCTUATION_HAUTE_ORDINAIRE = re.compile(r"(?<=\S) [:;?!](?=\s|$)")
_PONCTUATION_HAUTE_COLLEE = re.compile(r"(?<=[^\s])[:;?!](?=\s|$)")
_GUILLEMETS_SANS_INSECABLE = re.compile("«(?!\xa0)|(?<!\xa0)»")
_FORMULE_SANS_LIGNE_VIDE = re.compile(r"[^\n]\n(?:Bien cordialement|Cordialement|Bien à vous)\b")


def normaliser_typographie(texte: str) -> str:
    """Applique les règles de typographie française sans toucher aux mots ni aux liens ; idempotent."""
    liens: List[str] = []

    def garder(m: "re.Match[str]") -> str:
        liens.append(m.group(0))
        return f"\x00{len(liens) - 1}\x00"

    t = _LIEN.sub(garder, texte).replace("'", "’")
    t = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", t)
    t = re.sub(r"(?<=\w) +([,.])(?!\w)", r"\1", t)
    t = re.sub(r"(?<=\S)[ \xa0]?([:;?!])(?=\s|$)", NBSP + r"\1", t)
    t = re.sub(r"«[ \xa0]?", "«" + NBSP, t)
    t = re.sub(r"[ \xa0]?»", NBSP + "»", t)
    return re.sub("\x00(\\d+)\x00", lambda m: liens[int(m.group(1))], t)


def _tournures(texte: str) -> List[str]:
    bas = texte.lower()
    remarques = [f"« {t} » : {raison}" for t, raison in TOURNURES_A_EVITER if t in bas]
    for tournure, limite in LIMITES_OCCURRENCES.items():
        n = bas.count(tournure)
        if n > limite:
            remarques.append(f"« {tournure} » apparaît {n} fois (au plus {limite}) : varier")
    return remarques


def _typographie(texte: str) -> List[str]:
    sans_liens = re.sub(r"\S*(?:@|://)\S*", "lien", texte)
    remarques: List[str] = []
    if re.search(r"(?<=\S) {2,}(?=\S)", sans_liens):
        remarques.append("espaces doubles dans une phrase")
    if re.search(r"(?<=\w) [,.](?!\w)", sans_liens):
        remarques.append("espace avant une virgule ou un point")
    if re.search(r"[a-zà-ÿ][,;][A-Za-zÀ-ÿ]", sans_liens):
        remarques.append("espace manquant après une virgule ou un point-virgule")
    if "'" in texte and "’" in texte:
        remarques.append("apostrophes droites et courbes mélangées")
    if _PONCTUATION_HAUTE_ORDINAIRE.search(sans_liens):
        remarques.append("espace ordinaire avant : ; ? ou ! (mettre une espace insécable)")
    if _PONCTUATION_HAUTE_COLLEE.search(sans_liens):
        remarques.append("aucune espace avant : ; ? ou ! (mettre une espace insécable)")
    if _GUILLEMETS_SANS_INSECABLE.search(sans_liens):
        remarques.append("guillemets français sans espace insécable à l'intérieur")
    if _FORMULE_SANS_LIGNE_VIDE.search(texte):
        remarques.append("pas de ligne vide avant la formule finale")
    bas = texte.lower()
    remarques += [f"ligature manquante : « {m} » (œ)" for m in LIGATURES_OUBLIEES if m in bas]
    return remarques


def verifier_langue(texte: str) -> List[str]:
    """Défauts de langue d'un texte (liste vide si rien à signaler)."""
    remarques: List[str] = []
    if MODIFIEUR_MAL_RATTACHE.search(texte):
        remarques.append("adjectif mal rattaché : « une alternance, disponible… » dit que c'est l'alternance qui est "
                         "disponible ; écrire « je suis disponible… et je cherche une alternance »")
    return remarques + _tournures(texte) + _typographie(texte)


def _phrases(texte: str) -> List[str]:
    corps = FORMULE_DE_FIN.split(texte)[0]
    # Un retour à la ligne simple n'est qu'un repli de ligne (Gmail coupe vers 70 caractères) : on ne coupe
    # que sur la ponctuation finale et sur les paragraphes.
    brut = re.split(r"(?<=[.!?])\s+|\n\s*\n", corps)
    nettoyees = (re.sub(r"\s+", " ", p).strip() for p in brut)
    return [p for p in nettoyees if len(p.split()) >= MIN_MOTS_PHRASE]


def phrases_communes(mails: Dict[str, str], seuil: float = 0.85) -> List[Tuple[str, str, str]]:
    """(mail A, mail B, phrase) pour chaque phrase identique ou quasi identique entre deux mails d'un lot."""
    noms = list(mails)
    phrases = {n: _phrases(mails[n]) for n in noms}
    trouvees: List[Tuple[str, str, str]] = []
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            for pa in phrases[a]:
                if any(difflib.SequenceMatcher(None, pa.lower(), pb.lower()).ratio() >= seuil for pb in phrases[b]):
                    trouvees.append((a, b, pa))
    return trouvees


def fautes_orthographe(texte: str, dictionnaire: Optional[Any] = None) -> List[str]:
    """Mots inconnus du dictionnaire français (noms propres, adresses et mots autorisés exclus).

    `dictionnaire` doit offrir `unknown(mots)` ; par défaut `pyspellchecker`, ignoré s'il n'est pas installé.
    """
    if dictionnaire is None:
        try:
            from spellchecker import SpellChecker
        except ImportError:
            return []
        dictionnaire = SpellChecker(language="fr")
    sans_liens = re.sub(r"\S*(?:@|://)\S*", " ", texte)
    mots = re.findall(r"[A-Za-zÀ-ÿŒœ]+", sans_liens)
    # Les mots à majuscule initiale (noms de personnes et d'entreprises) ne sont pas dans un dictionnaire.
    candidats = [m for m in mots if len(m) > 2 and not m[0].isupper() and m.lower() not in MOTS_AUTORISES]
    return sorted(dictionnaire.unknown(candidats))
