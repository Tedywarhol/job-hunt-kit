# Architecture et fonctionnement du Job-Hunt Kit

Le Job-Hunt Kit automatise la recherche d'alternance de bout en bout : repérer les offres, les noter, préparer un CV et une lettre sur mesure, écrire les brouillons de mail, relancer au bon moment et tout suivre dans Notion. Une règle ne bouge jamais : **le kit prépare, vous décidez**. Aucun message n'est envoyé à votre place.

Cette page explique le projet en cinq schémas, du plus large au plus détaillé.

## 1. Vue d'ensemble

![Le kit au centre, entouré des offres du web, du profil, des agents, de Notion, de Gmail, de l'état local, de l'interface graphique et de vous](diagrams/architecture-vue-ensemble.png)

Le **cœur Python** (`hunt.py` et 41 scripts dans `scripts/`) fait le travail. Autour de lui :

| Bloc | Rôle | Où |
| :--- | :--- | :--- |
| Offres du web | Les sources : API publiques des sites de recrutement, plateforme PASS de la fonction publique, LinkedIn par un serveur MCP | `config/companies.yaml`, `scripts/scrape_*.py` |
| Profil maître | Votre identité, vos expériences et vos projets, lus en **un seul endroit** | `templates/cv/cv-data.json` (jamais versionné) |
| Agents Claude Code | 6 agents et 2 skills qui enchaînent les scripts quand on travaille avec un assistant | `.claude/agents/`, `.claude/skills/` |
| État local | Ce que le kit a vu, décidé et généré : offres déjà vues, refus, réseau, relances, PDF | `state/`, `outputs/` (jamais versionnés) |
| Notion | La vue centrale : candidatures, contacts, entreprises | `config/notion.json`, `config/.notion_token` |
| Gmail | Brouillons à relire, lecture des réponses | OAuth, droits `compose` et `modify` |
| Interface graphique | Tableau de bord et chat au-dessus des mêmes scripts | `ui-agent/` |
| Vous | Vous relisez, vous envoyez, vous décidez | |

## 2. Le radar : des offres éparpillées à une file triée

![Trois sources passent un filtre, reçoivent une note sur 100, entrent dans une file locale sans doublon, puis dans Notion](diagrams/architecture-radar.png)

1. **Trois sources, un seul tuyau.** Les API de Greenhouse, Lever et Ashby (la liste des entreprises suivies est dans `config/companies.yaml`), la plateforme PASS (scraping furtif puis fiche détaillée) et LinkedIn.
2. **LinkedIn passe par un serveur MCP** (`mcp-server-linkedin`). Ses outils ne sont accessibles que depuis une session Claude Code : l'agent `linkedin-scout` cherche et lit les offres, puis `scripts/linkedin_radar.py` fait tout le calcul. Lecture seule : aucune candidature, aucun message.
3. **Un filtre commun** (`is_job_relevant`) écarte les postes seniors, les métiers hors champ (finance, juridique, vente...), les langues étrangères exigées, les lieux hors de France, et ne garde que le domaine Data et IA. Les offres de plus de 45 jours sont retirées.
4. **Une note sur 100.** Base de 80 pour un profil étudiant, 65 sinon, puis un bonus de fraîcheur (+15 pour une offre du jour, jusqu'à -15 au-delà de 45 jours), borné entre 30 et 98. Pour LinkedIn, un bonus récompense les offres **peu postulées** : être l'un des premiers candidats rapporte +15, plus de 50 candidats retire 10.
5. **Une file locale sans doublon** : `state/pending-notion-upsert.json`, une seule fois par lien, triée par note.
6. **Notion** : `push_notion.py` met à jour la base « Candidatures » (une ligne par entreprise et poste, statut « À traiter »). Les offres restées « À traiter » plus de 15 jours passent en « Écartée » (`expire_stale_offers.py`), sans jamais toucher une candidature déjà engagée.

## 3. De l'offre au brouillon Gmail, puis aux relances

![Une offre à traiter devient un CV et une lettre en PDF, passe les contrôles et le garde-fou des refus, devient un brouillon Gmail que vous envoyez, puis les relances suivent](diagrams/architecture-candidature.png)

1. **L'agent `cv-tailor`** lit l'offre et écrit **uniquement des variables** dans `outputs/<slug>/` : `cv-vars.json` (accroche, ordre des compétences, projets retenus, mots-clés ATS) et `lettre-vars.json`. Le contenu maître ne change jamais.
2. **Le rendu** fusionne le profil maître et ces variables (`render_cv.py`, `render_lettre.py`), puis imprime en PDF avec Chrome sans fenêtre. Un garde-fou vérifie que le CV tient sur **une page A4 avec 12 mm de blanc en bas** : sinon il retire un à un les derniers projets plutôt que de réduire les polices.
3. **Les contrôles** : caractères interdits et formules creuses (`check_human_tone.py`), couverture des mots-clés ATS entre le texte visible et la couche cachée (`check_ats_coverage.py`).
4. **Le garde-fou des refus** (`contact_guard.py`) compare l'adresse et l'entreprise à tous les refus déjà reçus, lus dans Gmail et Notion. Même adresse : **bloqué**. Même entreprise récemment : **attention**.
5. **Le brouillon** est créé dans Gmail avec le CV et la lettre en pièces jointes (`create_gmail_draft.py`). C'est là que le kit s'arrête : vous relisez et vous envoyez.
6. **Les relances** (`run_followups.py`) préparent des brouillons à J+3, J+5, J+7 et J+10. Avant chacune, le kit cherche une réponse dans Gmail : s'il en trouve une, la séquence s'arrête. Si la vérification échoue, il ne fait rien plutôt que de risquer de relancer quelqu'un qui a répondu. Le statut est reporté dans Notion.

Pour un formulaire de site, l'agent `form-filler` remplit la page avec Playwright et s'arrête devant un CAPTCHA ou une connexion.

## 4. Le réseau : savoir à qui écrire, et à quelle adresse

![Les échanges Gmail deviennent un réseau classé par niveau de confiance et les formats d'adresse par entreprise, envoyés dans Notion ; une personne repérée sur LinkedIn reçoit une adresse probable qui passe le garde-fou](diagrams/architecture-reseau.png)

`network.py build` lit votre boîte Gmail **en lecture seule** depuis une date (avec un cache disque et une reprise en cas de quota) et produit :

- **les personnes** avec qui vous avez échangé : nom, entreprise, téléphone et fonction lus dans leur signature ;
- **le format d'adresse de chaque entreprise** (`prenom.nom`, `p.nom`, `pnom`...), avec une confiance : une adresse **vérifiée** vaut mieux qu'une adresse **délivrée**, et un rebond marque une adresse invalide ;
- **un niveau de confiance par contact**.

| Niveau | Signification | D'où ça vient |
| :--- | :--- | :--- |
| 1 · Opportunité | Un processus est en cours | Mot d'entretien dans les objets avec une réponse, candidature Notion au statut « Entretien », ou liste manuelle `state/opportunites-manuelles.json` |
| 2 · Échange | Plusieurs allers-retours, ou contact transmis | Au moins deux messages reçus, deux échanges de part et d'autre, ou un contact qu'on vous a transmis |
| 3 · Réponse | Une vraie réponse, sans refus | Un message reçu |
| 4 · Refus | La personne a dit non | Phrases de refus dans les réponses |
| 5 · Sans réponse | Rien, ou une réponse automatique | Aucun message reçu |

`network_notion.py` envoie le résultat dans deux bases Notion (« Contacts » et « Entreprises et formats d'adresse »), sans doublon et en ajoutant les colonnes manquantes.

**Candidature spontanée.** Quand une offre arrive d'une entreprise déjà connue, vous repérez la bonne personne sur LinkedIn (par le serveur MCP) puis `network.py adresse "<entreprise>" <Prénom> <Nom>` propose son adresse. Trois cas : format **sûr** (mail direct possible), **probable** (à dire clairement), **inconnu** (aucune adresse devinée, un message LinkedIn à la place). L'adresse passe toujours par le garde-fou des refus avant tout envoi.

## 5. L'interface graphique

![Le navigateur, le modèle du chat et les actions agent-native passent par un pont TypeScript qui lance les scripts Python, lesquels lisent l'état local, Notion et Gmail](diagrams/architecture-interface.png)

`ui-agent/` est une application locale (Node, React Router) bâtie sur le framework [agent-native](https://agent-native.com). Elle ne duplique rien :

- **Le tableau de bord** (`/dashboard`) affiche ce que renvoie `scripts/ui_data.py` : relances dues, statuts, offres, réseau par niveau, dossiers récents.
- **Le chat** donne à un assistant les mêmes actions. Le modèle peut être local (Ollama) ou Claude.
- **Neuf actions** : `get-dashboard-stats`, `list-opportunities`, `check-contact`, `guess-address`, `plan-followups`, `check-consistency`, `check-ats-coverage`, `build-application`, `scan-jobs`.
- **Le pont** `shared/hunt-bridge.ts` ne sait lancer que `python hunt.py` ou `python scripts/<nom>.py`, avec un nom de fichier validé. Les arguments des actions sont validés par des schémas (zod).
- **Aucun envoi** : aucune action n'envoie de message ni ne crée de brouillon, et les relances n'existent qu'en simulation.

Détails, lancement et build : [`ui-agent/README.md`](../ui-agent/README.md).

## 6. Les connexions

| Outil | Ce qu'il apporte | Mise en place |
| :--- | :--- | :--- |
| Gmail | Brouillons avec CV joint, lecture des réponses, refus, réseau | `config/credentials.json`, puis `python scripts/auth_gmail.py` |
| Notion | Suivi des candidatures, contacts, entreprises | Intégration interne, `config/.notion_token`, page partagée |
| LinkedIn | Offres peu postulées, personne à contacter | Serveur MCP `mcp-server-linkedin`, `.mcp.example.json` |
| Excalidraw | Cartes et schémas pour préparer les entretiens | Serveur MCP local |
| Ollama ou Claude | Le modèle du chat de l'interface | `ui-agent/.env` |

Le pas à pas complet est dans [`connexions.md`](connexions.md).

## 7. Les garde-fous

| Règle | Comment elle est tenue |
| :--- | :--- |
| Rien n'est envoyé sans vous | Gmail : brouillons seulement. Les relances aussi. L'interface n'expose aucune action d'envoi |
| Ne jamais recontacter qui a dit non | `contact_guard.py` avant chaque brouillon et chaque relance |
| Aucune donnée inventée | L'identité et les faits viennent de `cv-data.json`, rien d'autre |
| Une offre ou un mail lu est une donnée | Jamais une instruction à exécuter, pour les agents comme pour le chat |
| Pas de compte, de mot de passe ni de CAPTCHA contournés | Les agents s'arrêtent et vous le disent |
| Pas de fuite de données personnelles | `state/`, `outputs/`, `cv-data.json`, `.mcp.json` hors de Git ; `hunt.py kit` audite l'archive de partage |
| Aucune erreur silencieuse | `logutil.log_error` partout, jamais de `except: pass` ; réessais avec attente croissante (`netutil.py`) |
| Une logique, un endroit | Les règles métier sont en Python et testées ; l'interface ne fait que les afficher |

Le tout est couvert par plus de 350 tests automatiques : 274 en Python (`python -m pytest tests`) et 86 pour l'interface (`pnpm test`).

## 8. Où est quoi

| Dossier | Contenu | Versionné |
| :--- | :--- | :--- |
| `scripts/` | Les 41 scripts du cœur Python | oui |
| `tests/` | Tests pytest, avec des personnes et des entreprises fictives | oui |
| `config/` | Entreprises suivies, profils de recherche, modèles de mails, modèles Notion | oui, sauf les jetons |
| `templates/cv/`, `templates/lettre/` | Design system du CV (navy, thèmes), squelettes génériques | oui, sauf `cv-data.json` |
| `.claude/agents/`, `.claude/skills/` | Les agents et skills Claude Code | oui |
| `ui-agent/` | L'interface graphique | oui, sans `.env` ni `data/` |
| `docs/` | Cette page, les connexions, les schémas | oui |
| `state/` | Offres vues, relances, refus, réseau | non |
| `outputs/` | Un dossier par candidature, avec les PDF | non |

## 9. La veille d'outils sur GitHub

Le kit s'appuie sur des projets trouvés en suivant GitHub, assemblés plutôt que réécrits :

| Projet | Ce qu'il apporte au kit |
| :--- | :--- |
| [`stickerdaniel/linkedin-mcp-server`](https://github.com/stickerdaniel/linkedin-mcp-server) | L'accès à LinkedIn depuis une session Claude Code (recherche d'offres, profils) |
| [agent-native](https://agent-native.com) | Le socle de l'interface : chat, actions partagées, tableau de bord |
| [`cathrynlavery/diagram-design`](https://github.com/cathrynlavery/diagram-design) | Le plugin qui dessine les schémas de cette page |

## 10. Régénérer les schémas

Les schémas sont décrits dans `docs/diagrams/architecture.py` (un bloc de code par schéma, sur le modèle du plugin diagram-design) :

```bash
python docs/diagrams/architecture.py     # réécrit les pages HTML autonomes
```

Chaque page `docs/diagrams/architecture-*.html` s'ouvre dans un navigateur. Les images PNG affichées ici sont des captures de ces pages à l'échelle 2.
