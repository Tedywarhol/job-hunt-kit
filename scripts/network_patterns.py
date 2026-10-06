#!/usr/bin/env python3
"""Règles pures du réseau de contacts : noms, formats d'adresse, téléphone et fonction en signature.

Aucun appel réseau ici : tout se teste sur des chaînes (tests/test_network_patterns.py).
Utilisé par scripts/network.py (extraction Gmail, base Notion, construction d'adresse).
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# Formats d'adresse reconnus, du plus courant au plus rare. {p} prénom, {n} nom, {i} initiale du prénom.
FORMATS: Tuple[Tuple[str, str], ...] = (
    ("prenom.nom", "{p}.{n}"),
    ("p.nom", "{i}.{n}"),
    ("prenomnom", "{p}{n}"),
    ("pnom", "{i}{n}"),
    ("nom.prenom", "{n}.{p}"),
    ("prenom_nom", "{p}_{n}"),
    ("prenom-nom", "{p}-{n}"),
    ("nom", "{n}"),
    ("prenom", "{p}"),
    ("nom.p", "{n}.{i}"),
    ("nomp", "{n}{i}"),
)
# Boîtes génériques : jamais un format de personne.
GENERIC_LOCAL = re.compile(
    r"^(recrutement|recruitment|recrute|careers?|carrieres?|jobs?|emploi|rh|hr|humanresources|contact|info|"
    r"apprentissage|alternance|stage|talents?|candidatures?|service[._-]?\w*|team[._-]?\w*|hello|bonjour|admin|"
    r"support|dpo|rgpd|privacy|accueil|reclamations?|communication|presse|ventes?|compta|secretariat|direction|"
    r"admissions?|academ|webmaster|partenariats?|relations?[._-]?\w*)\b",
    re.I,
)
# Morceaux d'adresse qui désignent une fonction, pas une personne : « cfi.dpo@ », « support_dm@ ».
GENERIC_TOKENS = {
    "dpo", "rgpd", "gdpr", "privacy", "support", "contact", "info", "infos", "rh", "hr", "recrutement", "recruitment",
    "careers", "career", "jobs", "job", "emploi", "communication", "presse", "press", "ventes", "sales", "admissions",
    "academ", "noreply", "accueil", "secretariat", "direction", "compta", "factures", "marketing", "team", "service",
}


def is_generic(address: str) -> bool:
    """Boîte de fonction (recrutement@, cfi.dpo@, support_dm@...), jamais une personne."""
    local = address.split("@")[0].lower()
    return bool(GENERIC_LOCAL.match(local)) or any(t in GENERIC_TOKENS for t in re.split(r"[._-]", local))


PHONE_RE = re.compile(r"(?:\+33\s?\(?0?\)?\s?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b|\+\d{2,3}(?:[\s.-]?\d{2,4}){3,5}")
TITLE_WORDS = re.compile(
    r"\b(responsable|manager|directeur|directrice|director|head|lead|chef|charg[ée]e?|recrut|talent|rh\b|hr\b|"
    r"ressources humaines|consultant|ing[ée]nieur|engineer|officer|cto|ceo|coo|cdo|pr[ée]sident|fondat|founder|"
    r"partner|associ[ée]|analyst|scientist|product owner|business partner|assistante?|coordinat)",
    re.I,
)


def plain(text: str) -> str:
    """Minuscules, sans accent ni apostrophe ni espace : « Hélène D'Arc » -> « helenedarc »."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9-]", "", ascii_text.lower())


PARTICLES = {"de", "du", "des", "le", "la", "van", "von", "da", "di", "del", "ben", "el"}


def split_name(display: str, email: str) -> Tuple[str, str]:
    """(prénom, nom) depuis un nom d'affichage, l'adresse servant d'arbitre. Chaînes vides si inconnu."""
    if is_generic(email):
        return "", ""
    name = re.sub(r"\(.*?\)|\[.*?\]|\".*?\"|<.*?>", " ", display or "")
    name = re.split(r"\s[-|–]\s", name)[0].strip(" '\"")  # « Laura BLANC - Exemplia »
    if "@" in name or not name:
        return names_from_local(email)
    words = name.split()
    particle = next((i for i, w in enumerate(words) if i > 0 and w.lower() in PARTICLES), None)
    if particle is not None and "," not in name:
        return " ".join(words[:particle]).title(), " ".join(words[particle:])
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        return first.title(), last.title()
    words = name.split()
    if len(words) < 2:
        return names_from_local(email) if words and plain(words[0]) in plain(email.split("@")[0]) else ("", "")
    upper = [w for w in words if len(w) > 1 and w.isupper()]
    if upper and len(upper) < len(words):
        last = " ".join(upper)
        first = " ".join(w for w in words if w not in upper)
        return first.title(), last.title()
    local = plain(email.split("@")[0])
    if local.startswith(plain(words[-1])) and not local.startswith(plain(words[0])):
        return " ".join(words[1:]).title(), words[0].title()
    return " ".join(words[:-1]).title(), words[-1].title()


def names_from_local(email: str) -> Tuple[str, str]:
    """« prenom.nom@ » -> (Prénom, Nom) ; rien de sûr sinon."""
    local = email.split("@")[0].lower()
    if is_generic(email):
        return "", ""
    parts = [p for p in re.split(r"[._]", local) if p]
    if len(parts) == 2 and all(len(p) > 1 and p.isalpha() for p in parts):
        return parts[0].title(), parts[1].title()
    return "", ""


def candidates(first: str, last: str) -> Dict[str, str]:
    """Adresse (partie locale) que donnerait chaque format pour ce prénom et ce nom."""
    p, n = plain(first.split()[0]) if first else "", plain(last.replace(" ", ""))
    if not p or not n:
        return {}
    values = {"p": p, "n": n, "i": p[0]}
    return {fmt: template.format(**values) for fmt, template in FORMATS}


def detect_format(email: str, first: str, last: str) -> Optional[str]:
    """Format de cette adresse pour cette personne, ou None (générique ou non reconnu)."""
    local = email.split("@")[0].lower()
    if is_generic(email):
        return None
    variants = {local, local.replace("-", "")}
    for fmt, value in candidates(first, last).items():
        if value in variants or value.replace("-", "") in variants:
            return fmt
    return None


def build_address(fmt: str, first: str, last: str, domain: str) -> Optional[str]:
    local = candidates(first, last).get(fmt)
    return f"{local}@{domain}" if local else None


def best_format(evidence: List[Tuple[str, str]]) -> Tuple[Optional[str], str]:
    """(format, confiance) depuis des preuves (format, nature). Nature : vérifiée (la personne a écrit
    depuis cette adresse), délivrée (envoyée sans retour d'erreur), invalide (revenue en erreur)."""
    weights = {"vérifiée": 3, "délivrée": 1, "invalide": -3}
    scores: Dict[str, int] = {}
    for fmt, kind in evidence:
        scores[fmt] = scores.get(fmt, 0) + weights.get(kind, 0)
    if not scores or max(scores.values()) <= 0:
        return None, "inconnue"
    fmt = max(scores, key=lambda f: scores[f])
    verified = any(f == fmt and k == "vérifiée" for f, k in evidence)
    return fmt, ("sûre" if verified else "probable")


def signature_block(body: str, first: str, last: str) -> str:
    """Les lignes qui suivent la signature (nom de la personne), avant toute citation du message précédent."""
    body = re.split(r"\n\s*(?:Le .{5,120} a écrit|On .{5,120} wrote|De ?: |From: |-----Original|_{8,})", body)[0]
    lines = [line.strip() for line in body.splitlines()]
    keys = [plain(x) for x in (first, last) if x]
    for idx in range(len(lines) - 1, -1, -1):
        if keys and all(k in plain(lines[idx]) for k in keys if k):
            return "\n".join(lines[idx + 1: idx + 9])
    return "\n".join(lines[-8:])


def extract_phone(block: str) -> str:
    match = PHONE_RE.search(block or "")
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


def extract_title(block: str) -> str:
    for line in (block or "").splitlines():
        if 3 < len(line) < 90 and TITLE_WORDS.search(line) and "@" not in line and "http" not in line:
            return line.strip(" |*-")
    return ""


def address_status(email: str, sent: int, received: int, bounced: bool, relay: bool) -> str:
    """Ce qu'on sait d'une adresse : invalide, relais d'un outil de recrutement, vérifiée, délivrée."""
    if bounced:
        return "invalide"
    if relay:
        return "relais ATS"
    if received:
        return "vérifiée"
    return "délivrée" if sent else "citée"


TRUST_LEVELS = {1: "Opportunité", 2: "Échange", 3: "Réponse", 4: "Refus", 5: "Sans réponse"}
INTERVIEW = re.compile(
    r"(entretien|interview|zoom|teams|visio|rendez-vous|rencontre|introduction call|"
    r"suite à notre (échange|entretien|rencontre|appel)|échange téléphonique|premier échange)", re.I,
)


def trust_level(subjects: str, sent: int, received: int, relation: str, shared: bool, in_process: bool,
                free_mail: bool, manual: bool = False) -> int:
    """Niveau de confiance d'un contact, du plus chaud au plus froid (1 à 5) : 1 opportunité (mot d'entretien dans les
    objets avec une réponse ou une candidature au statut « Entretien », réponse d'une entreprise à ce statut, ou
    désignée à la main), 2 échange suivi ou contact transmis, 3 simple réponse, 4 refus, 5 sans réponse ou réponse
    automatique seulement."""
    replied = received > 0
    interview = bool(INTERVIEW.search(subjects))
    if manual or (not free_mail and ((interview and (replied or in_process)) or (in_process and replied))):
        return 1
    if shared:
        return 2
    if relation == "a refusé":
        return 4
    if received >= 2 or (replied and sent >= 2):
        return 2
    return 3 if replied else 5


def summarize_domains(people: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Une ligne par domaine : format d'adresse retenu, confiance, exemples, boîtes génériques, adresses invalides."""
    by_domain: Dict[str, List[Dict[str, str]]] = {}
    for person in people:
        by_domain.setdefault(person["email"].rsplit("@", 1)[-1], []).append(person)
    rows = []
    for domain, members in sorted(by_domain.items()):
        evidence, examples = [], []
        for person in members:
            fmt = detect_format(person["email"], person.get("prenom", ""), person.get("nom", ""))
            kind = {"vérifiée": "vérifiée", "délivrée": "délivrée", "invalide": "invalide"}.get(person["statut"])
            if fmt and kind:
                evidence.append((fmt, kind))
                if kind != "invalide":
                    examples.append(person["email"])
        fmt, confidence = best_format(evidence)
        rows.append({
            "domaine": domain,
            "entreprise": next((p["entreprise"] for p in members if p.get("entreprise")), ""),
            "format": fmt or "",
            "confiance": confidence,
            "exemples": ", ".join(examples[:3]),
            "contacts": str(len(members)),
            "generiques": ", ".join(p["email"] for p in members if is_generic(p["email"])),
            "invalides": ", ".join(p["email"] for p in members if p["statut"] == "invalide"),
        })
    return rows
