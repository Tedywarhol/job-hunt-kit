# Radar quotidien — prompt de la routine /schedule

Ce texte est le prompt à programmer via `/schedule` (exécution cloud quotidienne, ~7h).
Il orchestre le scrape → scoring → upsert Notion, sans intervention.

---

Exécute le Radar quotidien de recherche d'offres Data/IA.

1. Lance le sous-agent **job-scout** pour scraper les offres alternance/stage Data/IA
   (configs dans `config/search-profiles.yaml` et `config/companies.yaml`). Il déduplique
   contre `state/seen.json` et écrit les offres neuves dans `outputs/radar/`.

2. Passe les offres neuves au sous-agent **relevance-scorer** pour les noter /100 et
   décider `retenue` (seuil dans la config).

3. Upsert dans la base Notion (voir `config/notion.json`) via le MCP Notion ou `scripts/push_notion.py`. Une ligne par offre :
   - Entreprise, Poste, Type, Lien offre, Source, ATS, Lieu, Score, Contact recruteur,
     Notes matching.
   - Statut = `À traiter` si retenue, sinon `Écartée`.
   - Ne crée pas de doublon : si une offre (même clé) existe déjà, ne la réécris pas.

4. Écris un résumé du jour dans `logs/` : nb vus, neufs, retenus, écartés, erreurs de source.

Ne postule à rien ici (le Radar ne fait que détecter + ranger). Les candidatures se font
en session locale, séparément.
