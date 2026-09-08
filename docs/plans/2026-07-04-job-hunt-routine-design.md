# Job-Hunt Routine — Design

Date : 2026-07-04
Auteur : propriétaire du kit (avec Claude Code)
Statut : Validé (8 sections), prêt pour implémentation

## Objectif

Automatiser la recherche et la candidature à des offres **alternance + stage** en
Data / IA (GenAI, Data Scientist, Data Analyst, ML, Data Engineer) en France.
Routine quotidienne : scraper le web, détecter et scorer les offres, les ranger
dans Notion, puis postuler (semi-auto) avec CV + lettre personnalisés par offre,
et relancer les recruteurs.

## Décisions clés

| Sujet | Décision |
|---|---|
| Autonomie candidature | Semi-auto : préparation complète, stop avant Submit ; auto une fois un gabarit ATS validé |
| Sources | Welcome to the Jungle, Indeed/HelloWork, career pages ATS (Teamtailor/Lever/Greenhouse). Pas de LinkedIn (anti-scraping) |
| CV + lettre | Les deux variables. Template HTML/CSS → PDF, seuls les champs variables passent par le LLM |
| Suivi | Nouvelle base Notion "Candidatures Data/IA" |
| Déclencheur | Cloud quotidien (`/schedule`) pour scrape→Notion ; sessions locales pour l'apply (Chrome) |
| Recruteur | Brouillon email → envoi auto après validation du modèle. Séquence relances J+0/+3/+5/+7/+10 |
| Email d'envoi | Depuis l'email du candidat (`personal.email` dans `templates/cv/cv-data.json`) |

## Section 1 — Architecture d'ensemble

Deux étages séparés (contrainte : le scrape tourne dans le cloud, le remplissage de
formulaire exige le Chrome local connecté).

- **Étage 1 — Radar (cloud, quotidien).** `/schedule` scrape les sources, déduplique,
  score la pertinence, upsert Notion (statut `À traiter`).
- **Étage 2 — Candidature (local).** Session Claude Code : pour chaque ligne `À traiter`,
  génération CV+lettre PDF, remplissage Chrome, stop avant Submit (semi-auto), maj Notion,
  email recruteur.

Flux : `scrape → dédup → score → Notion → [session locale] → génère CV+lettre → remplis → valide → submit → maj Notion → email recruteur`.

Composants : Firecrawl/Apify/Scrapling (scrape), Notion MCP, Chrome MCP, Gmail MCP,
skill PDF, sous-agents dédiés.

## Section 2 — Radar (scraping quotidien cloud)

Déclencheur : cron quotidien (~7h). Config `config/search-profiles.yaml`
(mots-clés, types, localisation).

Stack scrape (fallback en cascade) :
1. **Firecrawl** (MCP/Docker) — primaire, search + extract structuré.
2. **Apify `rag-web-browser`** (connecté) — fallback Google Search + rendu navigateur.
3. **Scrapling** (à installer) — fallback stealth anti-bot (StealthyFetcher/Playwright).

Pipeline par source (WTTJ, Indeed/HelloWork, ATS via `config/companies.yaml`) :
extraction structurée JSON `{entreprise, poste, type, lieu, lien, description, contact_recruteur, ats_type}`.

- **Déduplication** : clé = hash(entreprise+poste+lieu), `state/seen.json`. Pas de re-score.
- **Scoring** : sous-agent léger note /100 (compétences, type contrat, séniorité, langue).
  Seuil (ex. ≥60) → Notion `À traiter` ; sinon `Écartée` + raison.
- **Sortie** : upsert Notion + log quotidien (vues / neuves / retenues).
- **Garde-fou** : source bloquée → log + continue les autres.

## Section 3 — Génération CV + lettre (HTML/CSS → PDF)

Contenu fixe figé dans le template ; seuls les champs variables remplis par offre.

```
templates/
  cv/    cv-base.html, cv.css, cv-data.json (profils stage + alternance)
  lettre/ lettre-base.html, lettre.css
outputs/{entreprise}-{poste}/ CV_*.pdf, Lettre_*.pdf
```

Champs variables CV : `accroche`, `competences_ordre`, `projets_mis_en_avant`,
`mots_cles_ats`. Lettre : `entreprise, poste, accroche_perso, arguments, cloture`
(passée au skill humanizer, règle "pas de tiret cadratin").

Génération PDF : template rempli → headless Chrome / skill `make-pdf`.
Reconstruction one-shot du CV HTML au setup (validé une fois).
Sous-agent : `cv-tailor` (offre + cv-data.json → champs remplis + PDF).

## Section 4 — Candidature locale (Chrome) + contrainte upload + semi-auto

**Contrainte :** `file_upload` Chrome MCP n'accepte que les fichiers attachés au chat,
le dossier `outputs/uploads` de session, ou un dossier connecté.
**Solution :** connecter le dossier projet (ou écrire les PDF dans le dossier outputs
autorisé) → upload auto sans réattacher.

Flux par offre `À traiter` :
1. `cv-tailor` génère CV+lettre PDF.
2. Ouverture du lien, détection ATS.
3. Remplissage : identité, email CV, tél, disponibilité, questions (depuis cv-data.json),
   upload CV, colle lettre.
4. Champ/question inédit → stop + demande (mémorisé pour la suite).
5. Semi-auto : 1er gabarit ATS → stop avant Submit + validation ; gabarit validé → Submit
   auto sur les suivantes du même ATS/type, chaque envoi loggé.
6. Maj Notion `Postulé` + date + PDF.

Garde-fous : jamais de compte/CAPTCHA/identifiants. Sous-agent `form-filler`.

## Section 5 — Outreach recruteur + relances

Séquence par recruteur (stop dès réponse) :

| Étape | Jour | Contenu |
|---|---|---|
| J+0 | candidature | Email initial : candidature déposée + match |
| J+3 | relance 1 | Rappel bref + 1 point fort |
| J+5 | relance 2 | Angle motivation / dispo |
| J+7 | relance 3 | Propose un échange |
| J+10 | relance 4 finale | Relance polie, porte ouverte |

Mécanique (cloud quotidien) : échéance atteinte ? → vérifie le thread Gmail →
si réponse → stop + Notion `Réponse reçue` + notif ; sinon génère+envoie la relance
depuis l'email du candidat. Après J+10 → `Relances terminées`.

Envoi depuis l'email du candidat (`personal.email`) : nécessite ce compte connecté au MCP ou
configuré en alias send-as (à vérifier au setup).

Garde-fous : envoi auto seulement après validation du modèle de séquence. 1 séquence/recruteur
(`state/outreach.json`). Sous-agent `recruiter-outreach`.

## Section 6 — Schéma Notion + sous-agents/skills

Base "Candidatures Data/IA" — colonnes : Entreprise (Title), Poste, Type (Select),
Statut (Select : À traiter/Postulé/Écartée/Réponse reçue/Entretien), Lien offre (URL),
Source (Select), ATS (Select), Lieu, Score (Number), Contact recruteur (Email),
Étape relance (Select), Date prochaine relance (Date), Date candidature (Date),
PDF (Files/URL), Notes matching (Text).

Sous-agents (isolés) : `job-scout`, `relevance-scorer`, `cv-tailor`, `form-filler`,
`recruiter-outreach`.

Skills : `humanizer` (existe), `pdf-render` (créer), `apply-routine` (orchestrateur, créer).

MCP : Notion, Chrome, Gmail, Firecrawl/Apify (via Docker).

## Section 7 — Garde-fous sécurité + coûts

Règles dures : pas de compte/mot de passe/CAPTCHA/données bancaires ; Submit auto seulement
sur gabarit validé ; email auto seulement après modèle validé ; 1 candidature/offre, 1 séquence/recruteur ;
contact seulement depuis offre réelle validée (anti prompt-injection : une offre = donnée, pas instruction).

Confidentialité : données perso dans `cv-data.json` local, jamais en query string, jamais
vers un endpoint suggéré par une page scrapée.

Coûts token : dédup `seen.json` (pas de re-score) ; scoring via modèle rapide (Haiku) ;
seuls les champs variables passent au LLM ; sous-agents en contexte isolé.
Fiabilité : source bloquée → log+continue ; champ inconnu → stop+demande ; logs dans `logs/`.

## Section 8 — Plan de mise en place

**Étape 0 — Prérequis :** connecter le dossier projet (upload) ; Gmail du candidat
(connexion ou alias) ; page parente Notion ; vérifier Firecrawl (Docker).

**Étape 1 — Fondations :** scaffold projet ; reconstruire CV HTML (2 profils, validé) ;
template lettre + `cv-data.json` ; créer base Notion ; installer Scrapling.

**Étape 2 — Radar :** config recherches ; `job-scout` + `relevance-scorer` (test 1 source) ;
routine `/schedule`.

**Étape 3 — Candidature :** `cv-tailor` + `pdf-render` ; `form-filler` + `apply-routine` ;
rodage semi-auto (validation gabarits ATS).

**Étape 4 — Outreach :** `recruiter-outreach` + séquence J+0→+10 ; validation modèle → envoi auto.

Ordre de valeur : Étapes 1-2 d'abord (flux d'offres scorées dans Notion), puis 3-4.
