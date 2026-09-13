# AGENTS.md

## Purpose

Automated job-hunt workspace (alternance 24 mois + stage 6 mois, Data/IA/GenAI/Tech roles in France) — kit générique, profil candidat lu depuis `templates/cv/cv-data.json` (généré par `init.py`).
Two-stage pipeline (see `docs/plans/2026-07-04-job-hunt-routine-design.md`):

1. **Radar (cloud/scraping):** scrape job sources (WTTJ, Indeed/HelloWork, ATS direct Greenhouse/Teamtailor/Ashby/Lever, PASS fonction publique) → dedupe → score → upsert Notion base "Candidatures Data/IA".
2. **Candidature (local sessions):** generate tailored CV + cover letter PDFs, fill Chrome forms (stop before Submit), create Gmail drafts with attached CV PDF, update Notion, manage recruiter follow-ups.

## Design System & CV Standards

- **Design System (`index.html` & `templates/cv/cv.css`):**
  - **Colors :** Navy `#323B4C` (sidebar & titres), blanc `#ffffff` (zone principale), slate `#f8fafc` & `#cbd5e1` (bannière & tags).
  - **Font :** `Montserrat, sans-serif` (Google Fonts).
  - **Sidebar gauche (65mm, Fond `#323B4C`) :** Nom, Titre badge, Contact, **Formation** (ECE Paris, CESI, CPGE MPSI, Baccalauréat Scientifique), Compétences clés réordonnables, Stack technique par catégories, Savoir-être, Langues (Anglais B2), Certifications, Intérêts.
  - **Zone principale (145mm, Fond `#ffffff`) :**
    - `.target-banner` : Titre du poste visé + tags dynamiques (durée 24 mois, rythme 3 sem./3 sem., lieu).
    - `Profil & Adéquation` : Accroche percutante intégrant le vocabulaire de l'offre.
    - `Expériences professionnelles` : 3 postes complets en grille CSS alignée (`.exp-header`), puces d'actions concrètes et résultats chiffrés (`✓ Bilan : ...`).
    - `Projets d'envergure` : **Les 6 projets d'envergure complets** (Big Data CHU, HR Analytics Turnover, Nooostress Marketplace, Assistant IA PLM, Workflow n8n & CRM IA, SaaS Propulse Scraping) avec timeline à nœuds circulaires, stack technique et puces structurées.
  - **Optimisation ATS (Option B) :**
    - Couche blanche invisible (1px, blanc sur blanc) en pied de page (`.ats-hidden-layer`) pour les mots-clés de l'offre.
    - Injection automatique des mots-clés, titre et sujet dans les métadonnées internes du PDF (`/Keywords`, `/Subject`, `/Title`, `/Author`).
  - **Layout :** Strict **1-page A4** (210mm x 297mm) print calibration (`@page { size: A4; margin: 0; }`).

- **Standards from `docs/guides/Guide CV_ZIARA Younous.md`:**
  - **Identité :** Prénom min./maj., NOM en majuscules (`Prénom NOM`). Localisation `Paris (75), France`. Pas d'adresse postale complète, pas d'âge, pas de nationalité (anti-biais).
  - **Formation :** Cycle Ingénieur Data Science & IA (ECE Paris / CESI) → CPGE MPSI → Baccalauréat Scientifique. Spécialité toujours alignée sur le poste visé.
  - **Expériences & Projets :** Jamais de mention « Stagiaire/Alternant » dans les titres d'expériences. Description d'action précise + résultat chiffré systématique (`✓ Bilan : ...`). Vrais noms de projets descriptifs.
  - **Langues :** Anglais avec niveau crédible (`Intermédiaire professionnel - B2`). Pas de mention du français pour les candidatures en France.
  - **ATS :** Reprise des mots-clés exacts de l'offre ciblée dans l'accroche, les compétences, la couche invisible et les métadonnées PDF.

## Onboarding & Initialisation du Kit

Pour initialiser le workspace ou déployer le kit sur une nouvelle machine :
```bash
python hunt.py init
```
Options disponibles :
- `--fichier <profil.json>` : initialise directement le profil candidat depuis un fichier JSON pré-rempli.
- `--theme <navy|emerald|bordeaux|#HEX>` : applique le thème graphique choisi.
- `--notion-token <token>` & `--notion-page-url <url>` : configure et crée automatiquement la base Notion "Candidatures".
- `--non-interactive` : exécution non-interactive (batch / CI).
- `python hunt.py kit` : produit l'archive `job-hunt-kit_<date>.zip` nettoyée de tout secret pour le partage.
- `python hunt.py test` : exécute la suite de tests automatisée (134 tests unitaires & intégration).
- `python hunt.py stats` : affiche le tableau de bord analytique de recherche et suivi des relances.

## Layout

- `hunt.py` — CLI unifiée du workspace (`init`, `apply`, `open`, `cv`, `lettre`, `scan`, `notion`, `draft`, `stats`, `status`, `kit`, `test`).
- `tests/` — Suite de tests automatisée pytest (134 tests) :
  - `test_ats_connectors.py` — Tests des parsers Greenhouse/Lever/Ashby, normalisation des dates ISO/Unix/FR, bonus de récence et filtres de pertinence (fonctions hors-scope, langue étrangère).
  - `test_dashboard.py` — Tests des indicateurs de fraîcheur, entonnoir de conversion, suivi CRM et statut réel Notion.
  - `test_profile.py` — Tests d'identité, nommage de fichiers, villes et dates en français.
  - `test_renders.py` — Tests des moteurs HTML/PDF, compétences et projets.
  - `test_security_kit.py` — Tests d'exclusion stricte de tout secret dans le kit de partage.
  - `test_cli.py` — Tests des sous-commandes de la CLI `hunt.py`.
  - `test_followups.py` — Tests du moteur de relances (mocks Gmail/Notion, jamais d'appel réel).
  - `test_notion_sync.py` — Tests de la couche Notion (`push_notion.py`), `urllib` mocké.
  - `test_check_consistency.py` — Tests du contrôle de cohérence, sur fixtures temporaires.
  - `test_netutil.py` — Tests du retry réseau (transitoire vs non-transitoire).
  - `test_ats_coverage.py` — Tests de la couverture ATS visible vs. cachée.
  - `test_human_tone.py` — Tests de la checklist de ton humain.
  - `test_companies_yaml_check.py` — Tests du diagnostic `companies.yaml`.
  - `test_response_rates.py` — Tests de l'analyse rétroactive du taux de réponse.
  - `test_extract_document_text.py` — Tests d'extraction de texte (PDF/DOCX/TXT/MD) pour l'import de profil.
- `scripts/` — Python pipeline :
  - `init.py` — Orchestrateur d'initialisation et configuration interactive du Job-Hunt Kit.
  - `init_notion_db.py` — Création automatique de la base Notion avec 15 colonnes via l'API REST.
  - `make_kit.py` — Empaqueteur d'archive de partage sécurisée (sans secrets ni données personnelles).
  - `profile.py` — Source unique d'identité et helpers de profil.
  - `logutil.py` — Logging minimal des erreurs non-fatales (`log_error`, stderr + `logs/errors.log`) : aucun `except: pass` silencieux dans le projet.
  - `scrape_ats_api.py` — Connecteur direct d'API publiques ATS (Greenhouse, Lever, Ashby) avec tri par fraîcheur ; radar canonique (branché sur `hunt.py scan`).
  - `dashboard.py` — Dashboard analytique console (entonnoir de conversion, KPIs de fraîcheur, CRM relances, statut réel Notion, relances en retard).
  - `run_followups.py` — Moteur de relances J+3/5/7/10 avec détection de réponse Gmail, mode brouillons uniquement (`--apply` pour agir, dry-run par défaut).
  - `check_consistency.py` — Contrôle de cohérence transactionnelle `outputs/` ↔ `state/outreach.json` ↔ Notion, rapport uniquement (ne modifie jamais rien).
  - `check_ats_coverage.py` — Couverture réelle des mots-clés ATS dans le texte visible du CV vs. la couche cachée (`--all` ou un slug).
  - `check_human_tone.py` — Checklist de ton humain (caractères interdits, formules creuses) pour lettres/emails ; remplace le skill "humanizer" absent de cet environnement.
  - `check_companies_yaml.py` — Diagnostic de `config/companies.yaml` : teste si chaque board ATS répond réellement, ne corrige jamais rien automatiquement.
  - `netutil.py` — Retry réseau avec backoff exponentiel (`with_retries`), pour les erreurs transitoires uniquement (jamais un 4xx).
  - `analyze_response_rates.py` — Analyse rétroactive du taux de réponse par ATS/source/tranche de score (lecture seule, Notion).
  - `extract_document_text.py` — Extraction déterministe du texte d'un CV/document (PDF/DOCX/TXT/MD) pour l'import de profil ; l'interprétation se fait via le skill `import-profile`, jamais par regex.
  - `build_application.py` — Orchestrateur de candidature (génère CV + lettre PDF par offre).
  - `render_cv.py` / `render_lettre.py` — Moteurs HTML→PDF (Chrome headless, Design System index.html, injection métadonnées PDF).
  - `create_gmail_draft.py` / `auth_gmail.py` / `generate_alternance_drafts.py` — Création de brouillons Gmail OAuth avec CV PDF joint ; `create_gmail_draft.py::find_reply` détecte les réponses recruteur.
  - `scrape_scrapling.py` / `scrape_pass.py` / `enrich_pass_offers.py` — Scrapers stealth (Scrapling) pour le web et la plateforme PASS.
  - `filter_alternance_pass.py` / `export_pass_csv.py` / `summary_pass.py` — Traitement, scoring de récence et export des offres PASS.
  - `notion_apply.py` / `push_notion.py` / `push_pass_to_notion.py` — Synchronisation API Notion REST (`push_notion.py` porte les helpers partagés : pagination, lecture de propriétés, recherche par entreprise+poste).
  - `deprecated/radar_run.py` — Ancien radar ATS, mis à l'écart le 2026-09-07 (doublon divergent de `scrape_ats_api.py`, cf. `docs/plans/2026-09-07-plan-amelioration.md` M0). Conservé pour référence, ne pas réintégrer.
- `templates/cv/` — `cv-data.template.json` (squelette modèle), `cv-data.json` (contenu maître local), `cv.css` (Design System Navy/Slate A4 thémable), `themes/` (navy, emerald, bordeaux).
- `templates/lettre/` — `lettre.css` (mise en page corporative coordonnée et thémable).
- `config/` — `companies.yaml` (20+ entreprises tech cibles ATS), `notion.template.json`, `notion.json`, `search-profiles.yaml`, `outreach-templates.md`.
  - **Secrets gitignorés :** `config/.notion_token`, `config/credentials.json`, `config/gmail_token.json`, `.env` — ne jamais les commiter ni les afficher en clair.
- `outputs/<entreprise-poste-slug>/` — un dossier par candidature (`CV_*.pdf`, `Lettre_*.pdf`, `cv-vars.json`, `lettre-vars.json`). Gitignoré. `lettre-vars.json` trace `lien` (URL de l'offre d'origine) depuis le 2026-09-07 quand il est connu — permet à `check_consistency.py` de relier le dossier à sa page Notion sans deviner sur un match texte entreprise/poste.
- `state/` — tracking & cache (`seen.json`, `pending-notion-upsert.json`, `pass_alternance_scored.json`, `outreach.json`, `qa-memory.json`). Gitignoré. `outreach.json` est lu ET écrit par `run_followups.py` (source de vérité locale de la séquence de relances, recoupée avec Notion).
- Root `index.html` — Page de référence visuelle du Design System CV.

## Key conventions

- Le contenu maître de base est dans `templates/cv/cv-data.json`. La personnalisation par offre se fait **exclusivement** via `outputs/<slug>/cv-vars.json` (titre, accroche, ordre des compétences, ordre des projets, mots-clés ATS) et `outputs/<slug>/lettre-vars.json`.
- Commande de génération principale : `python hunt.py apply <slug> --profile alternance|stage`.
- Contenu utilisateur en français soigné, accents et typographie Montserrat préservés.
- Normalisation systématique des dates de publication vers le format ISO (`YYYY-MM-DD`) avec injection de la date du jour si absente et calcul d'âge en jours (`age_jours`).
- Les colonnes Notion sont mappées dynamiquement via `config/notion.json`.
- Flux semi-automatique : les emails sont générés en brouillons Gmail prêts à l'envoi et les formulaires web sont vérifiés avant toute soumission.
- Toute exception rattrapée doit passer par `logutil.py::log_error()` (stderr + `logs/errors.log`) — jamais de `except: pass` silencieux (cf. `.claude/rules/00-core.mdc`).
- `run_followups.py` tourne en mode **brouillons uniquement** : il ne fait jamais d'envoi automatique, même avec `--apply`. Le passage à l'envoi auto est une décision produit distincte, pas encore prise.

## Sub-agents & Skills

- `.claude/agents/` : `job-scout`, `relevance-scorer`, `cv-tailor`, `form-filler`, `recruiter-outreach`.
- `.claude/skills/apply-routine` : Orchestrateur de déroulement des candidatures.
- `.claude/skills/import-profile` : Met à jour `templates/cv/cv-data.json` (profil, poste visé, domaine de recherche, expériences, projets, compétences) depuis un CV/document existant (`scripts/extract_document_text.py` pour l'extraction) ou une instruction directe — jamais d'écriture sans diff montré et confirmé.
- Voir aussi `docs/plans/2026-09-07-analyse-existant.md` et `docs/plans/2026-09-07-plan-amelioration.md` : audit de fiabilité du 2026-09-07 et journal des chantiers en cours (M0-M6).
- `.mcp.json` déclare le serveur MCP tiers `linkedin` ([`mcp-server-linkedin`](https://github.com/stickerdaniel/linkedin-mcp-server), optionnel) : `job-scout` l'utilise en lecture seule pour `search_jobs`/`get_job_details`, `recruiter-outreach` pour `search_people`/`get_company_employees`/`get_person_profile`. `send_message` et `connect_with_person` sont désactivés par défaut et gated par `config/linkedin-outreach.json:actif` (opt-in explicite, plafonds jour/semaine, une seule action par recruiter, confirmation à chaque envoi — cf. README, section LinkedIn, et `state/linkedin-outreach.json` pour le suivi).
