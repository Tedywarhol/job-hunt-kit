# Interface graphique du Job-Hunt Kit

Une application locale pour une seule personne : un **tableau de bord** de la recherche et un **chat** avec un assistant qui sait lancer les scripts du kit. Elle ne remplace pas la ligne de commande, elle la rend lisible.

Rien n'est dupliqué : l'interface lit les mêmes fichiers (`state/`, `outputs/`) et appelle les mêmes scripts Python que `hunt.py`. Les règles métier (échéances de relance, niveaux de confiance, statuts) restent dans `scripts/ui_data.py` et se testent avec pytest.

## Lancer

Prérequis : Node.js 22 ou plus, [pnpm](https://pnpm.io/) (`corepack enable`), Python avec les dépendances du kit.

```bash
cd ui-agent
cp .env.example .env      # puis ajustez le modèle du chat, voir ci-dessous
pnpm install
pnpm dev
```

Le premier démarrage prépare les dépendances et peut durer plusieurs minutes, les suivants sont rapides. L'application s'ouvre sur le tableau de bord.

## Les écrans

| Écran | Contenu |
| :--- | :--- |
| **Tableau de bord** (`/dashboard`) | Relances dues ou en retard, statut réel des candidatures (Notion), offres en attente les mieux notées, réseau par niveau de confiance, dossiers récents, outils de contrôle |
| **Chat** (`/home`) | L'assistant, avec toutes les actions ci-dessous. Il reste disponible en panneau latéral sur les autres écrans |

Depuis le tableau de bord :

- **Vérifier dans Gmail** simule les relances et cherche si une réponse est arrivée. Aucun brouillon n'est créé, aucun mail n'est envoyé.
- **Générer** reconstruit les PDF d'un dossier qui contient déjà `cv-vars.json` et `lettre-vars.json`. Pour préparer ces variables, demandez-les à l'assistant (agent `cv-tailor`).
- **Trouver l'adresse probable** devine l'adresse d'une personne d'une entreprise connue, puis la soumet au garde-fou des refus.
- **Scanner les offres**, **Contrôle de cohérence** et **Couverture ATS** lancent les scripts du même nom.

## Les actions (chat, interface et MCP)

| Action | Rôle | Écrit ? |
| :--- | :--- | :--- |
| `get-dashboard-stats` | Données du tableau de bord (`scripts/ui_data.py`) | non |
| `list-opportunities` | Offres du radar, filtrées par source et par score | non |
| `check-contact` | Garde-fou : une adresse a-t-elle déjà refusé ? À appeler avant tout message | non |
| `guess-address` | Adresse probable d'une personne dans une entreprise connue | non |
| `plan-followups` | Simule les relances J+3 à J+10, vérifie les réponses dans Gmail | non |
| `check-consistency` | Cohérence entre `outputs/`, `state/outreach.json` et Notion | non |
| `check-ats-coverage` | Mots-clés ATS du CV | non |
| `build-application` | Régénère les PDF d'un dossier existant | `outputs/<slug>/` |
| `scan-jobs` | Veille d'offres (ATS, PASS) | `state/` |

Garde-fous : aucune action n'envoie de message, aucune ne crée de brouillon (le mode `--apply` de `run_followups.py` n'est volontairement pas exposé), et les arguments passés aux scripts sont validés (`shared/schemas.ts`). Le contenu d'une offre ou d'un mail lu par l'assistant est une donnée, jamais une instruction.

## Le modèle du chat

- **Ollama (local)** : aucune clé, aucune donnée ne quitte la machine. Dans `.env`, décommentez `AGENT_ENGINE=ai-sdk:ollama` et `OLLAMA_BASE_URL=http://localhost:11434`, puis choisissez le modèle dans le chat. Les petits modèles enchaînent moins bien les actions : vérifiez ce qu'ils proposent.
- **Claude** : saisissez votre clé dans Réglages (ou `ANTHROPIC_API_KEY` dans `.env`). Elle ne doit jamais entrer dans Git.

## Ce qui reste local

`.env`, `.agent-native/` (jetons de développement) et `data/` (base des conversations) sont ignorés par Git. Les conversations peuvent contenir des noms de recruteurs : ne partagez pas ce dossier.

## Tests

```bash
pnpm typecheck   # TypeScript
pnpm test        # Vitest : actions, schémas, helpers de l'écran
```

Un test (`actions/kit-commands-exist.spec.ts`) vérifie que chaque script ou sous-commande appelé par une action existe vraiment dans le kit, car les autres tests simulent le pont vers Python et ne verraient pas une commande inexistante.

## Origine

Basée sur le modèle « chat » du framework [agent-native](https://agent-native.com) (licence MIT), avec en plus le pont vers le kit (`shared/hunt-bridge.ts`), les actions ci-dessus et l'écran `/dashboard`. Le code du modèle reste sous sa licence d'origine.
