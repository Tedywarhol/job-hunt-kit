# 🎯 Job-Hunt Kit

> **Système automatisé de veille, scoring et génération de candidatures sur-mesure (CV & lettre de motivation 1 page A4 calibrée, base Notion connectée, brouillons Gmail OAuth).**

---

## ⚡ Démarrage 1-Clic (Accessible à tous)

### 🖱️ Option 1 : Lancement direct sans ligne de commande
- **Sur Windows :** Double-cliquez simplement sur **[`hunt.bat`](hunt.bat)**.
- **Sur macOS / Linux :** Lancez `./hunt.sh` ou `python3 hunt.py`.

Un **Menu Interactif Convivial** s'ouvre pour vous guider pas-à-pas :

```text
================================================================
JOB-HUNT KIT — MENU PRINCIPAL
================================================================
  1. Generer une candidature sur-mesure (CV + Lettre PDF)
  2. Lancer la veille d'offres (ATS & PASS)
  3. Tableau de bord & Suivi des candidatures
  4. Preparer les brouillons d'emails Gmail
  5. Previsualiser mon CV PDF (Alternance / Stage)
  6. Synchroniser avec Notion
  7. Modifier mon profil ou theme graphique
  8. Verifier l'installation & Lancer les tests
  0. Quitter
================================================================
Choix [0-8] :
```

---

### 💻 Option 2 : Ligne de commande unifiée (`hunt.py`)

| Action | Commande | Description |
| :--- | :--- | :--- |
| **Menu Interactif** | `python hunt.py` | Ouvre l'assistant visuel guidé. |
| **Initialisation** | `python hunt.py init` | Configure votre profil, thème graphique et Notion. |
| **Prévisualiser CV** | `python hunt.py cv` | Compile et ouvre instantanément votre CV 1-page A4. |
| **Créer Candidature** | `python hunt.py apply` | Assistant guidé (crée le dossier, CV et lettre PDF). |
| **Veille Automatisée** | `python hunt.py scan` | Détecte les offres PASS & ATS triées par récence. |
| **Tableau de Bord** | `python hunt.py stats` | Entonnoir de conversion, KPIs et suivi des relances. |
| **Brouillons Gmail** | `python hunt.py draft` | Prépare les emails avec CV joint dans vos brouillons. |
| **Tests & Santé** | `python hunt.py test` | Exécute la suite de tests automatisée (134 tests). |
| **Pack de Partage** | `python hunt.py kit` | Génère un zip propre sans secrets prêt à envoyer. |

---

## 📐 Architecture & Fonctionnalités

Le kit repose sur un pipeline à 2 étapes :

```
┌────────────────────────────────────────────────────────┐
│ 1. RADAR (Veille & Scoring)                            │
│ Scrape (PASS, WTTJ, Indeed, ATS) ──► Déduplique ──►   │
│ Score /100 ──► Upsert Base Notion "Candidatures"       │
└───────────────────────────────────┬────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────┐
│ 2. CANDIDATURE (Génération ciblée & Envoi)             │
│ Lecture file Notion ──► Personnalisation CV + Lettre   │
│ ──► Rendu PDF A4 (Chrome) ──► Formulaires / Gmail     │
└────────────────────────────────────────────────────────┘
```

### Points forts du Design System CV
- **Strictement calibré pour 1 page A4** (210mm x 297mm, marges zéro au print).
- **Structure sidebar / zone principale** :
  - *Sidebar gauche (65mm)* : Nom, titre badge, contact, formation, compétences réordonnables, stack technique catégorisée, savoir-être, langues, certifications, intérêts.
  - *Zone principale (145mm)* : Bannière dynamique avec tags d'offre (durée, rythme, lieu), profil & accroche ciblée, timeline d'expériences professionnelles (avec bilans chiffrés `✓ Bilan : ...`), projets d'envergure complets.
- **Optimisation ATS (Applicant Tracking Systems)** :
  - Couche invisible blanche sur blanc (1px) en bas de page (`.ats-hidden-layer`) contenant les mots-clés de l'offre.
  - Injection automatique des mots-clés, auteur, titre et sujet dans les métadonnées internes du fichier PDF (`/Keywords`, `/Author`, `/Title`, `/Subject`).
- **Thèmes interchangeables** :
  - `navy` : `#323B4C` (Classique corporate - par défaut)
  - `emerald` : `#155E4C` (Moderne & dynamique)
  - `bordeaux` : `#7A1F2B` (Élégant & institutionnel)
  - Couleur personnalisée supportée (`#RRGGBB`).

---

## 🛠️ Commandes du quotidien

### 1. Veille & Offres de l'État (Plateforme PASS)
Le kit intègre une suite d'outils dédiés aux offres de la fonction publique (PASS) :

```bash
# 1. Scraper la liste des offres PASS selon vos filtres
python scripts/scrape_pass.py

# 2. Enrichir avec le détail des fiches et extraire les emails recruteurs
python scripts/enrich_pass_offers.py

# 3. Filtrer et noter les offres d'alternance / stage
python scripts/filter_alternance_pass.py

# 4. Pousser les offres retenues vers votre base Notion
python scripts/push_pass_to_notion.py

# 5. (Optionnel) Exporter les offres enrichies en CSV ou afficher une synthèse
python scripts/export_pass_csv.py
python scripts/summary_pass.py
```

### 2. Scraping web furtif (Scrapling)
Pour extraire le texte ou les éléments d'une annonce en contournant les protections :
```bash
python scripts/scrape_scrapling.py "https://example.com/job-offer" --stealth
```

### 3. Gestion de la file Notion
```bash
# Lister les offres au statut "À traiter" triées par score décroissant
python scripts/notion_apply.py list

# Marquer une offre comme postulée
python scripts/notion_apply.py mark --url "https://..." --statut Postulé --date 2026-09-01
```

### 4. Personnalisation & Génération CV + Lettre
Pour chaque offre, créez un dossier sous `outputs/<slug>/` (ex: `outputs/cartelis-consultant-data/`) contenant :
- `cv-vars.json` :
  ```json
  {
    "titre": "Consultant Data & IA",
    "accroche": "Diplômé en ingénierie Data Science, je conçois des pipelines ETL et modèles prédictifs à fort impact métier.",
    "competences_ordre": ["Data Engineering", "Machine Learning"],
    "projets_selection": ["Cloud Healthcare Unit", "HR Analytics"],
    "mots_cles_ats": ["Python", "SQL", "ETL", "Power BI", "Scikit-learn", "GCP"]
  }
  ```
- `lettre-vars.json` :
  ```json
  {
    "entreprise": "Cartelis",
    "poste": "Consultant Data & IA",
    "type": "alternance",
    "destinataire": "Madame, Monsieur",
    "objet": "Candidature au poste de Consultant Data & IA",
    "paragraphes": [
      "Votre offre de Consultant Data & IA a particulièrement retenu mon attention...",
      "Mon parcours m'a permis de développer une double compétence en modélisation et data engineering...",
      "Je serais ravi de vous rencontrer afin de vous exposer mes motivations."
    ]
  }
  ```

Puis lancez :
```bash
python hunt.py apply cartelis-consultant-data --profile alternance
```
Les fichiers `CV_<Prenom>_<NOM>.pdf` et `Lettre_<Prenom>_<NOM>.pdf` sont générés instantanément dans le dossier !

### 5. Création de brouillons Gmail (OAuth)
```bash
# Créer un brouillon ciblé avec CV en pièce jointe
python hunt.py draft \
  --to "recruteur@entreprise.com" \
  --subject "Candidature Alternance — Consultant Data" \
  --body "Bonjour, veuillez trouver ci-joint mon CV..." \
  --cv "outputs/cartelis-consultant-data/CV_Alexandre_DUPONT.pdf"

# Ou générer automatiquement les 5 meilleurs brouillons pour les offres PASS
python hunt.py draft --top 5
```

### 6. Relances automatiques & contrôle de cohérence
```bash
# Aperçu (dry-run, ne rien écrire) : qui a répondu, qui est dû pour une relance
python scripts/run_followups.py

# Applique : crée les brouillons J+3/5/7/10 dus, arrête la séquence sur réponse détectée,
# synchronise state/outreach.json et Notion. Mode brouillons uniquement : aucun envoi
# automatique tant que ce n'est pas explicitement changé dans le code.
python scripts/run_followups.py --apply

# Vérifie que outputs/, state/outreach.json et Notion racontent la même histoire
python scripts/check_consistency.py
```
`hunt.py stats` affiche aussi le statut réel des candidatures (lu directement dans Notion) et les relances en retard.

### 7. Mettre à jour votre profil depuis un CV existant
Vous avez déjà un CV (PDF, DOCX, TXT ou MD) et voulez importer votre profil, poste visé,
domaine de recherche, expériences, projets ou compétences dans le kit :
```bash
python hunt.py profile import chemin/vers/mon-cv.pdf
```
Extrait le texte du document. La fusion réelle dans `templates/cv/cv-data.json` se fait
ensuite avec Claude Code (`/import-profile chemin/vers/mon-cv.pdf`) : le skill compare le
contenu du document à votre profil actuel et vous montre le diff proposé — **rien n'est
jamais écrit sans confirmation explicite**, et aucune information absente du document
n'est inventée.

### 8. Partage du Kit sans secrets
Pour exporter une version propre du kit prête à être transmise à un ami ou collaborateur :
```bash
python hunt.py kit
```
Cette commande produit une archive `job-hunt-kit_<date>.zip` après avoir audité et garanti qu'aucun secret (`.notion_token`, `credentials.json`, `gmail_token.json`, `.env`, données privées) n'est inclus. L'audit scanne le contenu de **tous** les fichiers texte inclus (pas seulement `cv-data.json`) pour l'email et le téléphone réels du profil actif, chargés dynamiquement — jamais codés en dur dans le script lui-même.

---

## 🤖 Rôle des Sous-Agents & Skills (.claude)

Si vous utilisez un assistant IA compatible (comme Claude Code ou Antigravity) :
- **`job-scout`** : Scrape les annonces sur le web, extrait les champs structurés et déduplique contre `state/seen.json`.
- **`relevance-scorer`** : Évalue l'adéquation de chaque offre par rapport à votre profil `cv-data.json` sur 100 points.
- **`cv-tailor`** : Rédige automatiquement les fichiers `cv-vars.json` et `lettre-vars.json` et appelle `build_application.py`.
- **`form-filler`** : Remplit les formulaires de candidature en ligne (ATS) et uploade votre CV PDF via Playwright.
- **`recruiter-outreach`** : Rédige les emails d'accompagnement et séquence de relances (J+0, J+3, J+5, J+7, J+10).
- **Skill `apply-routine`** : Orchestrateur de bout en bout qui traite la file Notion offre par offre.
- **Skill `import-profile`** : Met à jour votre profil (identité, poste visé, domaine de recherche, expériences, projets, compétences) depuis un CV/document existant, jamais sans vous montrer le diff avant d'écrire.

Deux scripts déterministes (pas des agents IA, aucun coût de token) complètent le cycle de vie d'une candidature au-delà de l'envoi :
- **`scripts/run_followups.py`** : moteur de relances J+3/5/7/10 avec détection de réponse Gmail, mode brouillons uniquement.
- **`scripts/check_consistency.py`** : croise `outputs/`, `state/outreach.json` et Notion, signale les désynchronisations.

---

## 🔧 Dépannage & FAQ

### Chrome / Edge introuvable lors de la génération PDF
Si le script indique que Chrome est introuvable, définissez la variable d'environnement `CHROME_PATH` pointant vers votre exécutable :
- **Windows** : `$env:CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"`
- **Linux** : `export CHROME_PATH="/usr/bin/google-chrome"`
- **macOS** : `export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`

### Scraping stealth (`--stealth`, offres PASS) : navigateur introuvable
`pip install -r requirements.txt` installe les paquets Python (`patchright`, `playwright`)
mais jamais le binaire du navigateur lui-même (~300-500 Mo, mis en cache hors du venv).
Installez-le une fois avec :
```bash
python -m patchright install chromium
```
`python scripts/init.py` propose cette étape (optionnelle) à l'installation.

### Erreur OAuth Google / Gmail
1. Rendez-vous sur [Google Cloud Console](https://console.cloud.google.com/).
2. Créez un projet et activez l'API **Gmail**.
3. Dans *Identifiants*, créez un identifiant **Client OAuth 2.0** de type **Application pour ordinateur (Desktop App)**.
4. Téléchargez le fichier JSON et enregistrez-le sous `config/credentials.json`.
5. Lancez `python scripts/auth_gmail.py` pour valider l'accès via votre navigateur.

### Token Notion & Permissions
1. Rendez-vous sur [Notion Integrations](https://www.notion.so/my-integrations) et créez une intégration interne (token commençant par `ntn_...` ou `secret_...`).
2. Ouvrez la page Notion parente dans votre navigateur.
3. Cliquez sur `...` en haut à droite > **Connexions** > Ajoutez votre intégration.
4. Lancez `python scripts/init_notion_db.py --token <votre_token> --page-url <url_de_la_page>`.

### Exécution depuis n'importe quel sous-dossier
Tous les scripts sont conçus pour résoudre automatiquement la racine du projet (`ROOT`). Vous pouvez donc les exécuter depuis la racine ou depuis `scripts/` sans risque d'erreur de chemin.

---

## 📄 Licence

Ce kit est mis à disposition pour un usage personnel et professionnel. Libre à vous de l'adapter à vos besoins !
