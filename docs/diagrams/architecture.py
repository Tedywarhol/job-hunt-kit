#!/usr/bin/env python3
"""Génère les cinq schémas d'architecture du Job-Hunt Kit (docs/diagrams/architecture-*.html).

  python docs/diagrams/architecture.py        # réécrit les pages HTML
Les PNG de docs/architecture.md s'obtiennent en exportant ces pages (voir docs/architecture.md).
"""
import os
from typing import Callable, Dict

from diagram_kit import Diagram

HERE = os.path.dirname(os.path.abspath(__file__))


def overview() -> Diagram:
    d = Diagram("architecture-vue-ensemble", "Architecture · Job-Hunt Kit", "Le kit au centre, vos outils autour",
                "Vue d'ensemble : les offres du web et le profil alimentent le cœur Python, que pilotent des agents Claude Code "
                "et une interface graphique, et qui écrit dans l'état local, Notion et des brouillons Gmail que vous envoyez.")
    d.edge([(272, 124), (504, 124)], label="MCP LINKEDIN", at=(388, 124))
    d.edge([(272, 160), (388, 160), (388, 300), (504, 300)], label="API ATS, PASS", at=(388, 230), side="right")
    d.edge([(272, 336), (504, 336)], label="IDENTITÉ", at=(440, 336))
    d.edge([(640, 176), (640, 280)], label="PILOTENT", at=(640, 228), side="right")
    d.edge([(776, 292), (892, 292), (892, 136), (1008, 136)], label="SUIVI", at=(892, 214), side="right")
    d.edge([(776, 332), (1008, 332)], "accent", label="BROUILLONS", at=(892, 332))
    d.edge([(1008, 364), (776, 364)], "dashed", label="RÉPONSES", at=(892, 364), side="below")
    d.edge([(1124, 376), (1124, 496)], label="VOUS ENVOYEZ", at=(1124, 436), side="right")
    d.edge([(1008, 536), (776, 536)], label="CONSULTEZ", at=(892, 536))
    d.edge([(700, 496), (700, 392)], label="LANCE", at=(700, 444), side="right")
    d.edge([(504, 536), (272, 536)], label="LIT", at=(388, 536))
    d.edge([(580, 392), (580, 456), (156, 456), (156, 496)], label="ÉCRIT", at=(368, 456))
    d.node(40, 96, 232, 80, "external", "WEB", "Offres du web", ["Greenhouse, Lever, Ashby, PASS", "LinkedIn par serveur MCP"])
    d.node(504, 96, 272, 80, "backend", "AGENTS", "Agents Claude Code", ["6 agents et 2 skills", "ils appellent les scripts"])
    d.node(1008, 96, 232, 80, "external", "NOTION", "Notion", ["candidatures, contacts,", "entreprises"])
    d.node(40, 296, 232, 80, "store", "JSON", "Profil maître", ["cv-data.json", "seule source de l'identité"])
    d.node(504, 280, 272, 112, "focal", "PYTHON", "Cœur Python", ["hunt.py et 41 scripts", "radar, PDF, relances,", "réseau, garde-fou"])
    d.node(1008, 296, 232, 80, "external", "GMAIL", "Gmail", ["brouillons et réponses", "jamais d'envoi"])
    d.node(40, 496, 232, 80, "store", "ÉTAT", "État local", ["state/ et outputs/", "offres, refus, réseau, PDF"])
    d.node(504, 496, 272, 80, "backend", "UI", "Interface graphique", ["tableau de bord et chat", "sur agent-native"])
    d.node(1008, 496, 232, 80, "user", "VOUS", "Vous", ["relisez, envoyez, décidez"])
    d.note(["Rien ne part sans vous."], 1240, 624, "M 1180,606 L 1180,580", (1180, 580), "end")
    return d


def radar() -> Diagram:
    d = Diagram("architecture-radar", "Radar · de l'offre à Notion", "Le radar : des offres éparpillées à une file triée",
                "Trois sources d'offres passent le même filtre, reçoivent une note sur 100, sont dédupliquées dans une file locale "
                "puis poussées dans la base Notion Candidatures, dont les offres trop vieilles sont écartées automatiquement.")
    d.edge([(264, 136), (316, 136), (316, 216), (368, 216)])
    d.edge([(264, 264), (368, 264)])
    d.edge([(264, 392), (316, 392), (316, 312), (368, 312)])
    d.edge([(568, 264), (664, 264)], label="RETENUES", at=(616, 264))
    d.edge([(864, 264), (960, 264)], "accent", label="NOUVELLES", at=(912, 264))
    d.edge([(1100, 320), (1100, 432)], label="PUSH NOTION", at=(1100, 376), side="right")
    d.edge([(864, 480), (960, 480)], "dashed", label="15 JOURS", at=(912, 480))
    d.node(40, 96, 224, 80, "external", "API", "Sites de recrutement", ["Greenhouse, Lever, Ashby", "liste : companies.yaml"])
    d.node(40, 224, 224, 80, "external", "WEB", "PASS, fonction publique", ["scraping furtif", "puis fiche détaillée"])
    d.node(40, 352, 224, 80, "external", "MCP", "LinkedIn", ["agent linkedin-scout", "lecture seule, nb candidats"])
    d.node(368, 208, 200, 112, "backend", "FILTRE", "Filtre", ["domaine Data et IA, lieu", "ni senior ni hors métier", "âge 45 jours au plus"])
    d.node(664, 208, 200, 112, "focal", "SCORE", "Note sur 100", ["base 80 étudiant, 65 sinon", "fraîcheur : +15 à -15", "LinkedIn : peu de candidats"])
    d.node(960, 208, 280, 112, "store", "ÉTAT", "File locale", ["pending-notion-upsert.json", "une seule fois par lien (dédup)", "triée par note"])
    d.node(960, 432, 280, 96, "external", "NOTION", "Base Candidatures", ["une ligne par entreprise et poste", "statut « À traiter »"])
    d.node(664, 432, 200, 96, "optional", "AUTO", "Nettoyage", ["« À traiter » depuis 15 jours", "devient « Écartée »"])
    d.note(["Trois sources, un seul tuyau :", "mêmes filtres, mêmes notes, même file."], 368, 512, "M 468,492 L 468,324", (468, 324))
    return d


def candidature() -> Diagram:
    d = Diagram("architecture-candidature", "Candidature · de la file au brouillon", "De l'offre au brouillon Gmail, puis aux relances",
                "Une offre à traiter devient un CV et une lettre en PDF, passe les contrôles et le garde-fou des refus, "
                "devient un brouillon Gmail que vous relisez et envoyez, puis les relances J+3 à J+10 suivent et mettent Notion à jour.")
    d.edge([(476, 168), (476, 248)], label="IDENTITÉ", at=(476, 208), side="right")
    d.edge([(272, 288), (360, 288)], label="OFFRE", at=(316, 288))
    d.edge([(592, 288), (680, 288)], label="VARIABLES", at=(636, 288))
    d.edge([(912, 288), (1000, 288)], label="2 PDF", at=(956, 288))
    d.edge([(1120, 328), (1120, 448)], label="AVANT ENVOI", at=(1120, 388), side="right")
    d.edge([(1000, 488), (912, 488)], label="SI OK", at=(956, 488))
    d.edge([(680, 488), (592, 488)], label="RELISEZ", at=(636, 488))
    d.edge([(360, 488), (272, 488)], label="APRÈS ENVOI", at=(316, 488))
    d.edge([(156, 448), (156, 328)], "dashed", label="STATUT", at=(156, 388), side="right")
    d.node(360, 88, 232, 80, "store", "JSON", "Profil maître", ["cv-data.json", "identité lue en un seul endroit"])
    d.node(40, 248, 232, 80, "external", "NOTION", "Offres « À traiter »", ["file triée par note", "notion_apply.py list"])
    d.node(360, 248, 232, 80, "backend", "AGENT", "Agent cv-tailor", ["n'écrit que des variables", "accroche, projets, mots-clés"])
    d.node(680, 248, 232, 80, "backend", "PDF", "CV et lettre en PDF", ["Chrome sans fenêtre, 1 page A4", "12 mm de marge, sinon on retire"])
    d.node(1000, 248, 240, 80, "backend", "CHECK", "Contrôles", ["ton humain, signes interdits", "mots-clés ATS dans le texte"])
    d.node(1000, 448, 240, 80, "focal", "GUARD", "Garde-fou des refus", ["même adresse, même entreprise ?", "refus lus dans Gmail et Notion"])
    d.node(680, 448, 232, 80, "external", "GMAIL", "Brouillon Gmail", ["CV et lettre en pièces jointes", "jamais d'envoi automatique"])
    d.node(360, 448, 232, 80, "user", "VOUS", "Vous relisez et envoyez", ["rien ne part sans vous"])
    d.node(40, 448, 232, 80, "backend", "J+N", "Relances J+3 à J+10", ["brouillons seulement", "stop dès qu'une réponse arrive"])
    d.note(["Le brouillon attend votre relecture,", "le kit ne l'envoie jamais à votre place."], 592, 584, "M 476,556 L 476,532", (476, 532), "end")
    return d


def reseau() -> Diagram:
    d = Diagram("architecture-reseau", "Réseau · contacts et adresses", "Le réseau : savoir à qui écrire, et à quelle adresse",
                "Les échanges Gmail deviennent un réseau de contacts classés par niveau de confiance et le format d'adresse de chaque "
                "entreprise, envoyés dans Notion, puis une personne repérée sur LinkedIn reçoit une adresse probable qui passe le garde-fou.")
    d.edge([(256, 144), (368, 144)], label="LECTURE SEULE", at=(312, 144))
    d.edge([(584, 144), (696, 144)], label="CONTACTS", at=(640, 144))
    d.edge([(912, 144), (1024, 144)], label="PUSH", at=(968, 144))
    d.edge([(476, 296), (476, 200)], label="OPPORTUNITÉS", at=(476, 248), side="right")
    d.edge([(804, 184), (804, 456)], label="FORMATS", at=(804, 320), side="right")
    d.edge([(584, 496), (696, 496)], label="PERSONNE", at=(640, 496))
    d.edge([(912, 496), (1024, 496)], label="ADRESSE", at=(968, 496))
    d.node(40, 104, 216, 80, "external", "GMAIL", "Boîte Gmail", ["échanges depuis avril", "cache, reprise sur quota"])
    d.node(368, 88, 216, 112, "focal", "EXTRAIT", "network.py build", ["noms, entreprises, signatures", "niveau de confiance 1 à 5", "format d'adresse par domaine"])
    d.node(696, 104, 216, 80, "store", "JSON", "Base du réseau", ["state/network.json", "un proche : base à part"])
    d.node(1024, 104, 216, 80, "external", "NOTION", "Contacts, entreprises", ["une ligne par adresse", "niveau, priorité, format"])
    d.node(368, 296, 216, 80, "external", "SIGNAUX", "Autres signaux", ["Notion : statut Entretien", "liste manuelle de processus"])
    d.node(368, 456, 216, 80, "external", "MCP", "LinkedIn", ["personne repérée dans", "l'entreprise visée"])
    d.node(696, 456, 216, 80, "backend", "ADRESSE", "network.py adresse", ["prénom, nom, entreprise", "adresse et confiance"])
    d.node(1024, 456, 216, 80, "security", "GUARD", "Garde-fou des refus", ["avant toute candidature", "spontanée"])
    d.note(["Près de 800 contacts,", "du plus chaud au plus froid."], 40, 340, "M 232,322 Q 282,256 396,204", (396, 201))
    return d


def interface() -> Diagram:
    d = Diagram("architecture-interface", "Interface graphique · ui-agent", "L'interface : un écran et un chat qui lancent les scripts",
                "Le navigateur affiche le tableau de bord et le chat. Le modèle du chat appelle des actions agent-native, qui passent par "
                "un pont TypeScript pour lancer les scripts Python du kit, lesquels lisent l'état local, Notion et Gmail sans rien envoyer.")
    d.edge([(256, 336), (368, 336)], label="HTTP", at=(312, 336))
    d.edge([(148, 296), (148, 144), (368, 144)], label="MESSAGES", at=(258, 144))
    d.edge([(476, 184), (476, 296)], label="APPELLE", at=(476, 240), side="right")
    d.edge([(584, 336), (696, 336)], label="SCRIPTS", at=(640, 336))
    d.edge([(912, 336), (1024, 336)], label="PYTHON", at=(968, 336))
    d.edge([(1132, 376), (1132, 488)], label="LIT ET ÉCRIT", at=(1132, 432), side="right")
    d.edge([(1132, 296), (1132, 184)], label="API", at=(1132, 240), side="right")
    d.edge([(476, 488), (476, 376)], "dashed", label="BORNENT", at=(476, 432), side="right")
    d.node(40, 296, 216, 80, "user", "UI", "Votre navigateur", ["tableau de bord et chat", "React Router"])
    d.node(368, 104, 216, 80, "external", "LLM", "Modèle du chat", ["Ollama en local ou Claude", "appelle les actions"])
    d.node(368, 296, 216, 80, "focal", "ACTIONS", "Actions agent-native", ["9 actions du kit", "arguments validés (zod)"])
    d.node(696, 296, 216, 80, "backend", "PONT", "hunt-bridge.ts", ["lance scripts/nom.py", "nom de fichier validé"])
    d.node(1024, 296, 216, 80, "backend", "PYTHON", "Scripts du kit", ["ui_data, contact_guard,", "network, run_followups"])
    d.node(1024, 488, 216, 80, "store", "ÉTAT", "state/ et outputs/", ["fichiers locaux du kit", "jamais dans Git"])
    d.node(1024, 104, 216, 80, "external", "API", "Notion et Gmail", ["statuts réels, réponses", "jetons du kit"])
    d.node(368, 488, 216, 80, "security", "RÈGLES", "Aucun envoi", ["ni message, ni brouillon", "relances en simulation"])
    d.note(["Les calculs restent en Python :", "l'écran ne fait que les afficher."], 696, 528, "M 804,506 L 804,380", (804, 380))
    return d


DIAGRAMS: Dict[str, Callable[[], Diagram]] = {
    "vue-ensemble": overview, "radar": radar, "candidature": candidature, "reseau": reseau, "interface": interface,
}

if __name__ == "__main__":
    for name, build in DIAGRAMS.items():
        path = os.path.join(HERE, f"architecture-{name}.html")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(build().page())
        print("écrit", os.path.relpath(path))
