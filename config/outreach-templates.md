# Modèle de séquence recruteur (à valider une fois)

Envoi depuis {{email}}. Placeholders : {entreprise}, {poste}, {recruteur}.
Ton naturel et chaleureux, sans tiret cadratin ni « & ». Personnalisé par offre au moment de l'envoi.

Règle de ton (2026-10-03, après un retour « trop sec, sans cœur, trop vite ») : des phrases simples et
sans jargon, mais jamais de mail nu. Toujours une salutation avec le nom quand on le connaît, une phrase
d'attention (« J'espère que vous allez bien »), un remerciement, un vœu de fin et « Bien cordialement ».
Pas de flatterie ni de formule creuse, pas de liste sèche de métiers : une personne écrit à une autre.
Vérifier avec `python scripts/check_human_tone.py --text "<corps>"` (caractères interdits, formules
creuses, politesse).

## J+0 — Email initial (le plus consistant)
Doit mettre en avant : le besoin du poste, les compétences qui y répondent, l'enthousiasme et la
motivation à rejoindre l'équipe. {besoin_poste} = 1 phrase reformulant la mission de l'offre ;
{competences_match} = les compétences clés du candidat qui collent à l'offre.

**Objet :** Candidature au poste de {poste} - {{nom}}

Bonjour{recruteur},

J'espère que vous allez bien. Je me permets de vous écrire au sujet de ma candidature au poste de {poste}
chez {entreprise}, que je viens de déposer sur votre site.

Je suis {formation}, et je recherche {type_contrat}. Ce poste m'intéresse particulièrement, car
{besoin_poste}. Mon parcours y répond sur des points concrets : {competences_match}.

Je serais très heureux de pouvoir vous rencontrer, en visio ou sur place, pour vous parler de ma candidature
et de ce que je pourrais apporter à votre équipe.

Je vous remercie par avance pour l'attention que vous porterez à ma candidature, et vous souhaite une très
bonne journée.

Bien cordialement,
{{nom}}
{{email}} · {{telephone}}

## J+3 — Relance 1
**Objet :** Re: Candidature au poste de {poste}

Bonjour,

J'espère que vous allez bien. Je me permets de revenir vers vous au sujet de ma candidature au poste de
{poste} chez {entreprise}, que je vous ai adressée il y a quelques jours.

Je sais que vous recevez sans doute beaucoup de candidatures, et je vous remercie du temps que vous consacrez
à la mienne. Ce poste m'intéresse vraiment, et je serais heureux d'en parler avec vous quand cela vous conviendra.

Bien cordialement,
{{nom}}

## J+5 — Relance 2
**Objet :** Re: Candidature au poste de {poste}

Bonjour,

Je vous écris à nouveau car le poste de {poste} chez {entreprise} m'intéresse toujours autant. Je suis disponible
rapidement et je m'adapte volontiers à votre calendrier, si un premier échange est possible.

Je vous remercie de votre attention et vous souhaite une très bonne journée.

Bien cordialement,
{{nom}}

## J+7 — Relance 3
**Objet :** Re: Candidature au poste de {poste}

Bonjour,

Auriez-vous quelques minutes pour un court échange au sujet du poste de {poste} ? Je peux m'adapter à votre
agenda, par téléphone ou en visio, au moment qui vous arrange le mieux.

Je vous remercie beaucoup d'avance pour votre retour et vous souhaite une excellente semaine.

Bien cordialement,
{{nom}}

## J+10 — Relance finale
**Objet :** Re: Candidature au poste de {poste}

Bonjour,

Je vous écris une dernière fois au sujet de ma candidature au poste de {poste} chez {entreprise}. Si le moment
n'est pas le bon, ou si le poste est déjà pourvu, je le comprends tout à fait, et je vous remercie sincèrement
du temps que vous avez consacré à ma candidature.

Je reste à votre disposition si une autre opportunité se présente, et je vous souhaite une très bonne continuation.

Bien cordialement,
{{nom}}
