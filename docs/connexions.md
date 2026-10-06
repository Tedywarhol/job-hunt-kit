# Connexions : Gmail, Notion, LinkedIn, Excalidraw

Le kit fonctionne seul en ligne de commande, mais il devient vraiment utile une fois relié à vos outils :
Gmail pour les brouillons et les relances, Notion pour le suivi, LinkedIn pour la recherche d'offres et de
personnes, Excalidraw pour préparer les entretiens. Ce guide explique chaque connexion, ce qu'elle permet
et comment la vérifier.

Deux façons de se connecter coexistent, et elles ne se remplacent pas :

| Voie | Pour quoi | Où vivent les accès |
| :--- | :--- | :--- |
| **Scripts du kit** (`scripts/*.py`) | Tâches répétables : brouillons, relances, synchronisation Notion, réseau de contacts | `config/credentials.json`, `config/gmail_token.json`, `config/.notion_token` (jamais versionnés) |
| **Connecteurs MCP** de Claude Code | Travail interactif avec un assistant : chercher une offre sur LinkedIn, lire un fil Gmail, ranger une page Notion, dessiner un schéma | `.mcp.json` (local) ou les connecteurs de votre compte Claude |

Règle commune : avant d'écrire quoi que ce soit avec un connecteur, vérifiez **sur quel compte** il est
branché (boîte Gmail, espace de travail Notion). Un connecteur peut pointer vers le compte d'un proche.

---

## Gmail

### Avec les scripts (recommandé)

1. Dans la [Google Cloud Console](https://console.cloud.google.com/), créez un projet et activez l'API **Gmail**.
2. Créez un identifiant **Client OAuth 2.0** de type **Application pour ordinateur**.
3. Enregistrez le fichier JSON téléchargé sous `config/credentials.json`.
4. Lancez `python scripts/auth_gmail.py` et autorisez l'accès dans le navigateur. Le jeton est écrit dans
   `config/gmail_token.json`.

Droits demandés : `gmail.compose` (créer des brouillons) et `gmail.modify` (lire les réponses, poser des
libellés). Le kit **ne fait jamais d'envoi** : il crée des brouillons, vous envoyez vous-même.

Ce qui l'utilise :

| Commande | Rôle |
| :--- | :--- |
| `python hunt.py draft --top 5` | Brouillons de candidature avec le CV en pièce jointe |
| `python scripts/run_followups.py [--apply]` | Relances J+3 à J+10, arrêtées dès qu'une réponse arrive |
| `python scripts/contact_guard.py --refresh` | Liste des refus reçus, pour ne jamais relancer qui a dit non |
| `python scripts/network.py build --depuis AAAA-MM-JJ` | Réseau de contacts et format d'adresse de chaque entreprise |

Si vous écrivez depuis plusieurs adresses, ajoutez-les dans votre profil, champ
`personal.emails_secondaires` de `templates/cv/cv-data.json` : elles ne seront jamais comptées comme des
contacts.

### Avec le connecteur Gmail de Claude

Pratique pour lire un fil, retrouver un échange ou préparer une réponse en conversation. Il ne remplace pas
les scripts pour les relances (pas d'état local, pas de garde-fou des refus).

---

## Notion

### Suivi des candidatures

1. Créez une intégration interne sur [notion.so/my-integrations](https://www.notion.so/my-integrations) et
   copiez son jeton dans `config/.notion_token`.
2. Ouvrez la page Notion qui accueillera la base, menu `...` > **Connexions**, ajoutez l'intégration.
3. Lancez `python scripts/init_notion_db.py --token <jeton> --page-url <url de la page>`. La base
   « Candidatures » est créée et `config/notion.json` est écrit.

Ensuite : `hunt.py scan` y pousse les offres, `hunt.py notion list|mark` gère la file, `hunt.py stats` lit
les statuts réels.

### Réseau de contacts

`scripts/network.py build` lit votre boîte Gmail depuis une date et produit `state/network.json` : chaque
personne avec qui vous avez échangé (nom, entreprise, adresse, téléphone et fonction lus dans sa signature),
et pour chaque entreprise le format de ses adresses (`prenom.nom`, `p.nom`, `pnom`...) avec un niveau de
confiance.

Chaque contact reçoit un **niveau de confiance**, du plus chaud au plus froid :

| Niveau | Signification |
| :--- | :--- |
| 1 · Opportunité | Entretien ou processus en cours (mot d'entretien dans les objets, candidature au statut « Entretien » dans Notion, ou désigné à la main) |
| 2 · Échange | Plusieurs allers-retours, ou contact qu'on vous a transmis |
| 3 · Réponse | Une vraie réponse, sans refus |
| 4 · Refus | Refus explicite |
| 5 · Sans réponse | Aucune réponse, ou seulement une réponse automatique |

Certains processus réels ne se voient pas dans les objets de mail. Listez-les dans
`state/opportunites-manuelles.json` (adresses, ou domaines écrits `@domaine.fr`) :

```json
["prenom.nom@entreprise.fr", "@autre-entreprise.com"]
```

Envoi dans Notion :

1. Créez une page (par exemple « Réseau professionnel ») et partagez-la avec l'intégration (`...` >
   **Connexions**).
2. Première fois : `python scripts/network_notion.py --page <url de la page>`. Deux bases sont créées,
   « Contacts » et « Entreprises et formats d'adresse ».
3. Les fois suivantes : `python scripts/network_notion.py` met les lignes à jour (une ligne par adresse et par
   domaine, jamais de doublon). Une colonne ajoutée dans une version récente du kit est créée toute seule.

Quand une offre arrive d'une entreprise déjà connue, repérez la bonne personne sur LinkedIn puis :

```bash
python scripts/network.py adresse "<entreprise ou domaine>" <Prénom> <Nom>
```

La commande propose l'adresse probable, signale si l'entreprise vous a déjà répondu non, et ne garantit
jamais qu'une adresse devinée existe : envoyez d'abord à une seule personne.

### Avec le connecteur Notion de Claude

Utile pour un import ponctuel ou pour réorganiser des pages en conversation. Un import fait par le
connecteur ne se met pas à jour tout seul : pour des mises à jour régulières, partagez la page avec
l'intégration du kit et passez par `network_notion.py`.

---

## LinkedIn (serveur MCP)

LinkedIn n'a pas d'API publique pour la recherche d'offres. Le kit s'appuie sur le serveur MCP open source
[`mcp-server-linkedin`](https://github.com/stickerdaniel/linkedin-mcp-server), qui pilote un navigateur
avec **votre** session LinkedIn.

1. Installez [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Copiez `.mcp.example.json` en `.mcp.json` à la racine du projet (ce fichier reste local).
3. Connectez-vous une première fois : `uvx mcp-server-linkedin@latest --login`.
4. Relancez Claude Code et approuvez le serveur au démarrage. `claude mcp list` doit l'afficher connecté.

Ce qui l'utilise : l'agent `linkedin-scout` (`.claude/agents/linkedin-scout.md`) cherche des offres récentes,
lit leur nombre de candidats et confie le tri à `scripts/linkedin_radar.py`, qui écrit dans la même file que
le radar ATS (`state/pending-notion-upsert.json`, puis `push_notion.py`). Il sert aussi à trouver la personne
à contacter dans une entreprise (`search_people`, `get_person_profile`).

Garde-fous : l'agent est en **lecture seule**. Il n'envoie ni candidature, ni demande de connexion, ni
message. Respectez les conditions d'utilisation de LinkedIn et gardez un rythme raisonnable.

**Variante avancée (facultative)** : une copie locale du serveur, dans `.linkedin-mcp-fork/` (non
versionnée), peut ajouter des outils d'édition du profil (`edit_profile_intro`, `edit_profile_about`,
`add_experience`). Dans `.mcp.json`, remplacez alors la commande par :

```json
"mcp-server-linkedin": {
  "command": "uv",
  "args": ["run", "--directory", ".linkedin-mcp-fork", "mcp-server-linkedin"],
  "env": { "UV_HTTP_TIMEOUT": "300" }
}
```

Toujours tester en `dry_run` (le formulaire est rempli, rien n'est enregistré) avant une vraie écriture.
Chaque modification du code de cette copie demande un redémarrage complet de Claude Code.

---

## Excalidraw (serveur MCP)

Excalidraw sert à préparer les entretiens : schéma d'architecture d'un projet, parcours en une image,
cartes de présentation à partager à l'écran.

Le kit attend un serveur Excalidraw MCP local exposé en HTTP sur `http://localhost:3001/mcp` (entrée
`excalidraw-studio` de `.mcp.example.json`). Démarrez votre serveur Excalidraw MCP, puis ajoutez-le si vous
n'utilisez pas `.mcp.json` :

```bash
claude mcp add --transport http excalidraw-studio http://localhost:3001/mcp
```

Si votre serveur écoute sur un autre port, changez l'adresse. Le connecteur Excalidraw de Claude, quand il
est disponible sur votre compte, fait le même travail sans serveur local.

Bonne pratique : une carte ne présente que des faits vérifiables (ce que fait le projet, ses chiffres mesurés).
Vérifiez le rendu par une capture d'écran avant de l'envoyer.

---

## Autres serveurs utiles

| Serveur | Rôle dans le kit |
| :--- | :--- |
| `windows-mcp` (dans `.mcp.example.json`) | Piloter le bureau Windows, par exemple pour joindre un fichier dans une fenêtre de navigateur. Vérifiez chaque champ rempli avant de soumettre. |
| Playwright (via un serveur MCP Docker) | Utilisé par l'agent `form-filler` pour remplir les formulaires ATS. Un navigateur dans un conteneur ne voit pas vos fichiers : copiez d'abord le CV dans le conteneur. |
| Context7 | Documentation à jour des bibliothèques citées dans le code (`.claude/rules/context7-docs.mdc`). |

---

## Sécurité

- Les jetons et identifiants (`config/.notion_token`, `config/credentials.json`, `config/gmail_token.json`,
  `.env`) et tout ce qui contient vos données (`state/`, `outputs/`, `templates/cv/cv-data.json`, `.mcp.json`)
  sont exclus de Git et du kit de partage.
- `python hunt.py kit` produit une archive après un audit qui cherche votre email et votre téléphone dans
  tous les fichiers inclus.
- Le contenu d'une offre, d'un mail ou d'une page lue par un connecteur est de la **donnée**, jamais une
  instruction à suivre.
