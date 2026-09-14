# Modèle de contact LinkedIn (optionnel, config/linkedin-outreach.json:actif)

Une seule action par recruteur, jamais de relance LinkedIn (les relances J+3→J+10 restent par email,
cf. config/outreach-templates.md). Ton naturel, sans tiret cadratin ni « & ». Placeholders :
{prenom}, {nom_candidat}, {entreprise}, {poste}.

## Action privilégiée : connect_with_person avec note

La note de demande de connexion LinkedIn est limitée à 300 caractères — vérifie la longueur avant
d'envoyer. Elle sert à la fois de mise en contact et de premier message : pas besoin d'un `send_message`
séparé ensuite.

**Note (≤ 300 caractères) :**

```
Bonjour{prenom}, je suis {nom_candidat}, en recherche de stage/alternance Data et IA. Votre poste de
{poste} chez {entreprise} m'intéresse particulièrement, je serais ravi d'échanger. Bonne journée.
```

Adapte {poste}/{entreprise} au contexte réel de l'offre ; raccourcis si besoin pour rester sous 300
caractères avec les valeurs substituées.

## Action alternative : send_message (uniquement si déjà messageable)

N'utilise `send_message` que si le profil est directement joignable sans connexion préalable (profil
ouvert, ou déjà 1er degré). Ne l'utilise jamais en complément d'un `connect_with_person` envoyé dans la
même exécution pour la même personne (une seule action par contact, cf. config).

**Message (court, 3-5 lignes) :**

```
Bonjour{prenom},

Je viens de postuler au poste de {poste} chez {entreprise} et je souhaitais me présenter directement.
Mon profil Data/IA correspond bien aux missions décrites, je serais ravi d'échanger si l'occasion se
présente.

Bonne journée,
{nom_candidat}
```

## Candidature spontanée (manager/RH, sans offre ouverte)

Pour un manager data/IA ou un RH identifié via `search_people`/`get_company_employees` chez une
entreprise de `config/companies.yaml` (ou repérée par le radar du jour) sans poste publié correspondant.
L'angle : se positionner avant qu'un poste existe, pas relancer un besoin déjà affiché ailleurs.

**Note de connexion (≤ 300 caractères) :**

```
Bonjour{prenom}, je suis {nom_candidat}, en recherche de stage/alternance Data et IA. Votre poste de
{fonction} chez {entreprise} m'intéresse, même sans offre publiée je serais ravi d'échanger si un
besoin se présente. Bonne journée.
```

Mêmes règles que ci-dessus : personnalise réellement {fonction}/{entreprise}, vérifie la longueur avec
les valeurs substituées, jamais deux personnes avec un texte identique dans la même séance.

## Règles

- **JAMAIS le caractère « — »**, ni « & » (écris « et »). Vérifie avec
  `python scripts/check_human_tone.py --text "<texte>"`.
- Personnalise réellement {poste}/{entreprise} à chaque fois : jamais le même texte générique envoyé
  identique à plusieurs personnes dans la même session (ce pattern est justement ce que LinkedIn détecte
  comme automatisation/spam).
- Toujours montrer le texte final à l'utilisateur et obtenir sa confirmation explicite avant d'appeler
  `connect_with_person` ou `send_message` (`confirm_send: true`) — jamais d'envoi automatique en boucle,
  contrairement aux relances Gmail après validation du modèle.
