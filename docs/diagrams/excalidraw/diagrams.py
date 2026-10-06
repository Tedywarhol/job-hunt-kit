"""Les six schémas du Job-Hunt Kit, décrits avec kit.Canvas (positions en unités Excalidraw)."""
from typing import Dict

from kit import Canvas

FLOW = "#e8590c"   # orange du flux principal


def pipeline() -> Canvas:
    c = Canvas("pipeline", 1280, 640, "Du radar au suivi, en trois temps", "Le kit prépare, vous décidez.")
    radar = c.node(40, 150, 360, "web", "Radar", ["trouve les offres du web", "les note sur 100", "les range dans Notion"],
                   ["linkedin", "python", "notion"], h=210)
    cand = c.node(460, 150, 360, "python", "Candidature", ["CV et lettre sur mesure en PDF", "garde-fou : jamais deux fois non",
                  "brouillon dans Gmail"], ["claude", "chrome", "gmail"], h=210)
    suivi = c.node(880, 150, 360, "data", "Suivi", ["relances à J+3, J+5, J+7 et J+10", "stop dès qu'on vous répond",
                   "statut mis à jour dans Notion"], ["gmail", "notion"], h=210)
    for i, n in enumerate((radar, cand, suivi), start=1):
        c.badge(n.x - 12, n.y - 16, i)
    c.arrow([radar.right(), cand.left()], color=FLOW)
    c.arrow([cand.right(), suivi.left()], color=FLOW)
    c.node(40, 420, 1200, "you", "Vous relisez, vous envoyez, vous décidez",
           ["Rien ne part sans vous : le kit prépare des brouillons, jamais d'envoi."], h=120)
    return c


def overview() -> Canvas:
    c = Canvas("overview", 1280, 990, "Le kit au centre, vos outils autour", "Ce que le projet relie, et où vivent les données.")
    c.zone(40, 330, 220, 280, "Sur le web", "#1971c2")
    c.zone(350, 140, 590, 620, "Sur votre ordinateur", "#f08c00")
    c.zone(1030, 140, 210, 620, "Vos services", "#1971c2")
    profil = c.node(370, 190, 255, "data", "Profil maître", ["cv-data.json", "l'identité en un seul endroit"], h=160)
    agents = c.node(665, 190, 255, "agent", "Agents Claude Code", ["6 agents et 2 skills", "ils appellent les scripts"], ["claude"])
    coeur = c.node(410, 390, 470, "python", "Cœur Python", ["hunt.py et 41 scripts", "radar, PDF, relances, réseau, garde-fou"], ["python"])
    offres = c.node(55, coeur.y, 190, "web", "Offres du web", ["ATS, PASS, LinkedIn", "par serveur MCP"], ["linkedin", "mcp"])
    etat = c.node(370, 590, 255, "data", "État local", ["state/ et outputs/", "offres, refus, réseau, PDF"], h=160)
    ui = c.node(665, 590, 255, "ui", "Interface graphique", ["tableau de bord et chat", "sur agent-native"], ["react", "typescript"])
    notion = c.node(1045, 190, 180, "web", "Notion", ["suivi, contacts,", "entreprises"], ["notion"])
    gmail = c.node(1045, coeur.y, 180, "web", "Gmail", ["brouillons, réponses", "jamais d'envoi"], ["gmail"])
    vous = c.node(1030, 810, 210, "you", "Vous", ["relisez, envoyez,", "décidez"], h=110)
    c.arrow([offres.right(), coeur.left()], "API, MCP", at=0.36, color=FLOW)
    c.arrow([profil.bottom(-40), (profil.bottom(-40)[0], coeur.y)], "identité", "right")
    c.arrow([agents.bottom(), (agents.bottom()[0], coeur.y)], "pilotent", "right")
    c.arrow([coeur.bottom(-130), (coeur.bottom(-130)[0], etat.y)], "écrit", "right")
    c.arrow([ui.top(), (ui.top()[0], coeur.y + coeur.h)], "lance", "right")
    c.arrow([ui.left(), etat.right()])
    mid = coeur.y + coeur.h / 2
    c.arrow([coeur.right(-64), (965, mid - 64), (965, notion.y + notion.h / 2), notion.left()], "suivi", "right", segment=1, at=0.5)
    c.arrow([coeur.right(-12), gmail.left(-12)], "brouillon", at=0.636, color=FLOW)
    c.arrow([gmail.left(30), coeur.right(30)], "réponses", "below", at=0.364, dashed=True)
    c.arrow([gmail.bottom(), (gmail.bottom()[0], vous.y)], "à envoyer", "right")
    c.arrow([vous.left(), (ui.x + ui.w / 2, vous.y + vous.h / 2), ui.bottom()], "vous consultez", "above")
    c.legend(950)
    return c


def radar() -> Canvas:
    c = Canvas("radar", 1280, 830, "Le radar : des offres éparpillées à une file triée", "Trois sources, un seul tuyau.")
    ats = c.node(40, 170, 250, "web", "Sites de recrutement", ["Greenhouse, Lever, Ashby", "liste : companies.yaml"], h=146)
    pas = c.node(40, 336, 250, "web", "PASS", ["fonction publique", "scraping, puis fiche"], h=146)
    lin = c.node(40, 502, 250, "web", "LinkedIn", ["agent linkedin-scout", "lecture seule"], ["linkedin", "mcp"])
    filtre = c.node(350, 316, 240, "python", "Filtre", ["domaine Data et IA, lieu", "ni senior ni hors métier", "45 jours au plus"], ["python"], h=186)
    score = c.node(690, 316, 240, "python", "Note sur 100", ["80 étudiant, 65 sinon", "fraîcheur : +15 à -15", "bonus : peu de candidats"], ["python"], h=186)
    fichier = c.node(1030, 316, 210, "data", "File locale", ["offres sans doublon", "triées par note"], h=186)
    notion = c.node(1030, 570, 210, "web", "Base Candidatures", ["une ligne par offre", "statut « À traiter »"], ["notion"])
    menage = c.node(690, 570, 240, "auto", "Nettoyage", ["« À traiter » depuis 15 j", "passe en « Écartée »"], h=notion.h)
    mid = filtre.y + filtre.h / 2
    c.arrow([ats.right(), (320, ats.y + ats.h / 2), (320, mid - 40), (filtre.x, mid - 40)])
    c.arrow([pas.right(), (filtre.x, mid)])
    c.arrow([lin.right(), (320, lin.y + lin.h / 2), (320, mid + 40), (filtre.x, mid + 40)])
    c.arrow([filtre.right(), score.left()], "retenues", color=FLOW)
    c.arrow([score.right(), fichier.left()], "nouvelles", color=FLOW)
    c.arrow([fichier.bottom(), notion.top()], "vers Notion", "right")
    c.arrow([menage.right(), notion.left()], "écarte", dashed=True)
    c.text(350, 720, "Mêmes filtres, mêmes notes,\nmême file pour les trois sources.", 22, "#e8590c")
    c.arrow([(470, 714), (470, filtre.y + filtre.h)], color="#e8590c")
    c.legend(790)
    return c


def candidature() -> Canvas:
    c = Canvas("candidature", 1280, 860, "De l'offre au brouillon Gmail, puis aux relances", "Huit étapes, un seul geste humain : envoyer.")
    xs = (25, 355, 685, 1015)
    profil = c.node(xs[1], 130, 240, "data", "Profil maître", ["cv-data.json", "identité en un seul endroit"], h=110)
    a1 = c.node(xs[0], 300, 240, "web", "Offres à traiter", ["file triée par note", "notion_apply.py list"], ["notion"])
    a2 = c.node(xs[1], 300, 240, "agent", "Agent cv-tailor", ["n'écrit que des variables", "accroche, projets, ATS"], ["claude"])
    a3 = c.node(xs[2], 300, 240, "python", "CV et lettre en PDF", ["Chrome sans fenêtre", "1 page A4, 12 mm de marge"], ["chrome"])
    a4 = c.node(xs[3], 300, 240, "python", "Contrôles", ["ton humain et caractères", "mots-clés ATS visibles"], ["python"])
    b5 = c.node(xs[3], 540, 240, "guard", "Garde-fou des refus", ["adresse ou entreprise", "déjà refusée ?", "lu dans Gmail et Notion"], h=a4.h)
    b6 = c.node(xs[2], 540, 240, "web", "Brouillon Gmail", ["CV et lettre jointes", "jamais d'envoi automatique"], ["gmail"])
    b7 = c.node(xs[1], 540, 240, "you", "Vous envoyez", ["après relecture", "rien ne part sans vous"], h=a4.h)
    b8 = c.node(xs[0], 540, 240, "python", "Relances J+3 à J+10", ["brouillons seulement", "stop si une réponse arrive"], ["python", "gmail"])
    for i, n in enumerate((a1, a2, a3, a4, b5, b6, b7, b8), start=1):
        c.badge(n.x - 12, n.y - 16, i)
    c.arrow([profil.bottom(), a2.top()], "identité", "right")
    c.arrow([a1.right(), a2.left()], "offre", color=FLOW)
    c.arrow([a2.right(), a3.left()], "variables", color=FLOW)
    c.arrow([a3.right(), a4.left()], "2 PDF", color=FLOW)
    c.arrow([a4.bottom(), b5.top()], "avant envoi", "right", color=FLOW)
    c.arrow([b5.left(), b6.right()], "si OK", color=FLOW)
    c.arrow([b6.left(), b7.right()], "relisez", color=FLOW)
    c.arrow([b7.left(), b8.right()], "ensuite")
    c.arrow([b8.top(), a1.bottom()], "statut dans Notion", "right", dashed=True)
    c.text(330, 744, "Le brouillon attend votre relecture :\nle kit ne l'envoie jamais à votre place.", 22, "#0c8599")
    c.arrow([(475, 738), (475, b7.y + b7.h)], color="#0c8599")
    c.legend(820)
    return c


def network() -> Canvas:
    c = Canvas("network", 1280, 1000, "Le réseau : savoir à qui écrire, et à quelle adresse", "Gmail en lecture seule devient une base de contacts.")
    xs = (40, 360, 680, 1000)
    gmail = c.node(xs[0], 170, 220, "web", "Boîte Gmail", ["échanges depuis avril", "en lecture seule"], ["gmail"], h=186)
    extr = c.node(xs[1], 170, 220, "python", "network.py build", ["noms et signatures", "niveau de confiance 1 à 5", "formats par domaine"], ["python"], h=186)
    base = c.node(xs[2], 170, 220, "data", "Base du réseau", ["state/network.json", "un proche : base à part"], h=186)
    notion = c.node(xs[3], 170, 220, "web", "Contacts, formats", ["une ligne par adresse", "niveau et priorité"], ["notion"], h=186)
    sig = c.node(xs[1], 420, 220, "web", "Autres signaux", ["Notion : statut Entretien", "liste manuelle"], ["notion"])
    lin = c.node(xs[1], 650, 220, "web", "LinkedIn", ["personne repérée dans", "l'entreprise visée"], ["linkedin", "mcp"])
    adr = c.node(xs[2], 650, 220, "python", "network.py adresse", ["prénom, nom, entreprise", "adresse et confiance"], ["python"])
    guard = c.node(xs[3], 650, 220, "guard", "Garde-fou", ["refus déjà reçus ?", "avant toute candidature"], h=adr.h)
    c.arrow([gmail.right(), extr.left()], "lecture", color=FLOW)
    c.arrow([extr.right(), base.left()], "contacts", color=FLOW)
    c.arrow([base.right(), notion.left()], "push")
    c.arrow([sig.top(), extr.bottom()], "opportunités", "right")
    c.arrow([base.bottom(), adr.top()], "formats d'adresse", "right")
    c.arrow([lin.right(), adr.left()], "personne")
    c.arrow([adr.right(), guard.left()], "adresse")
    c.text(40, 850, "Chaque contact reçoit un niveau de confiance, du plus chaud au plus froid :", 22, "#1e1e1e")
    for i, (label, fill, stroke) in enumerate((("1 · Opportunité", "#b2f2bb", "#2f9e44"), ("2 · Échange", "#d3f9d8", "#51cf66"),
                                                ("3 · Réponse", "#fff3bf", "#f08c00"), ("4 · Refus", "#ffc9c9", "#e03131"),
                                                ("5 · Sans réponse", "#e9ecef", "#868e96"))):
        x = 40 + i * 244
        c.layers["text"].append({"type": "rectangle", "id": c._id("v"), "x": x, "y": 896, "width": 224, "height": 52,
                                 "backgroundColor": fill, "fillStyle": "solid", "strokeColor": stroke, "strokeWidth": 2,
                                 "roughness": 1, "roundness": {"type": 3},
                                 "label": {"text": label, "fontSize": 20, "fontFamily": 5, "strokeColor": "#1e1e1e"}})
    return c


def interface() -> Canvas:
    c = Canvas("interface", 1280, 900, "L'interface : un écran et un chat qui lancent les scripts", "Rien n'est dupliqué : l'écran affiche, Python calcule.")
    xs = (40, 350, 700, 1020)
    nav = c.node(xs[0], 400, 230, "ui", "Votre navigateur", ["tableau de bord et chat", "React Router"], ["react", "typescript"])
    llm = c.node(xs[1], 170, 250, "agent", "Modèle du chat", ["Ollama en local ou Claude", "appelle les actions"], ["ollama", "claude"])
    act = c.node(xs[1], 400, 250, "ui", "Actions agent-native", ["9 actions du kit", "arguments validés (zod)"], h=nav.h)
    pont = c.node(xs[2], 400, 250, "ui", "hunt-bridge.ts", ["lance scripts/nom.py", "nom de fichier validé"], ["typescript"])
    scripts = c.node(xs[3], 400, 220, "python", "Scripts du kit", ["ui_data, contact_guard,", "network, run_followups"], ["python"])
    api = c.node(xs[3], 170, 220, "web", "Notion et Gmail", ["statuts réels, réponses", "jetons du kit"], ["notion", "gmail"])
    etat = c.node(xs[3], 640, 220, "data", "state/ et outputs/", ["fichiers locaux du kit", "jamais dans Git"], h=scripts.h)
    regles = c.node(xs[1], 640, 250, "guard", "Aucun envoi", ["ni message, ni brouillon", "relances en simulation"], h=nav.h)
    c.arrow([nav.right(), act.left()], "HTTP")
    c.arrow([nav.top(), (nav.top()[0], llm.y + llm.h / 2), llm.left()], "messages", segment=1, at=0.5)
    c.arrow([llm.bottom(), act.top()], "appelle", "right")
    c.arrow([act.right(), pont.left()], "scripts", color=FLOW)
    c.arrow([pont.right(), scripts.left()], "python")
    c.arrow([scripts.bottom(), etat.top()], "lit et écrit", "right")
    c.arrow([scripts.top(), api.bottom()], "API", "right")
    c.arrow([regles.top(), act.bottom()], "bornent", "right", dashed=True)
    c.text(700, 650, "Les calculs restent\nen Python : l'écran\nne fait que les afficher.", 22, "#6741d9")
    c.arrow([(825, 644), (825, pont.y + pont.h)], color="#6741d9")
    c.legend(860)
    return c


def build_all() -> Dict[str, Canvas]:
    # nom du fichier PNG dans docs/diagrams/ -> schéma
    built = {"pipeline": pipeline(), "architecture-vue-ensemble": overview(), "architecture-radar": radar(),
             "architecture-candidature": candidature(), "architecture-reseau": network(), "architecture-interface": interface()}
    return {name: canvas.check() for name, canvas in built.items()}
