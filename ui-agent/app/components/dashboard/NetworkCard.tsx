import { useActionMutation } from "@agent-native/core/client/hooks";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import type { NetworkSummary } from "../../../shared/dashboard-types";
import { ActionOutput } from "./ActionOutput";
import { orderRows, TRUST_ORDER } from "./format";
import { StatBars } from "./StatBars";

const LEVEL_BAR: Record<string, string> = {
  Opportunité: "bg-emerald-600",
  Échange: "bg-emerald-500/70",
  Réponse: "bg-foreground/70",
  Refus: "bg-destructive/60",
  "Sans réponse": "bg-muted-foreground/40",
};

function AddressFinder() {
  const guess = useActionMutation("guess-address");
  const [fields, setFields] = useState({ entreprise: "", prenom: "", nom: "" });

  function submit(event: FormEvent) {
    event.preventDefault();
    guess.mutate(fields);
  }

  const complete = Object.values(fields).every((value) => value.trim().length > 0);
  return (
    <details className="group rounded-md border border-border px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium">Trouver l'adresse probable d'une personne</summary>
      <form onSubmit={submit} className="mt-3 grid gap-2 sm:grid-cols-3">
        <Input
          aria-label="Entreprise"
          placeholder="Entreprise ou domaine"
          value={fields.entreprise}
          onChange={(e) => setFields({ ...fields, entreprise: e.target.value })}
        />
        <Input
          aria-label="Prénom"
          placeholder="Prénom"
          value={fields.prenom}
          onChange={(e) => setFields({ ...fields, prenom: e.target.value })}
        />
        <Input
          aria-label="Nom"
          placeholder="Nom"
          value={fields.nom}
          onChange={(e) => setFields({ ...fields, nom: e.target.value })}
        />
        <div className="sm:col-span-3">
          <Button type="submit" size="sm" disabled={!complete || guess.isPending}>
            {guess.isPending ? "Recherche…" : "Chercher"}
          </Button>
          <span className="ml-3 text-xs text-muted-foreground">
            Une adresse devinée n'est jamais garantie : écrivez d'abord à une seule personne.
          </span>
        </div>
      </form>
      {guess.isError && <ActionOutput title="Échec" text={guess.error.message} failed />}
      {guess.data && (
        <ActionOutput title="Résultat" text={guess.data.report || guess.data.stderr || ""} failed={!guess.data.success} />
      )}
    </details>
  );
}

export function NetworkCard({ network, loading }: { network: NetworkSummary | null | undefined; loading: boolean }) {
  const rows = network ? orderRows(network.par_niveau, TRUST_ORDER) : [];
  return (
    <Card className="md:col-span-2">
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Réseau de contacts</CardTitle>
        <CardDescription>
          {network
            ? `${network.contacts} contacts dans ${network.entreprises} entreprises, base du ${network.genere_le}. ${network.refus} adresses ont déjà refusé.`
            : loading
              ? "Chargement…"
              : "Pas de réseau : lancez python scripts/network.py build --depuis AAAA-MM-JJ."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {network && !network.niveaux_calcules && (
          <p className="rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
            Cette base date d'avant les niveaux de confiance. Reconstruisez-la : python scripts/network.py build --depuis
            AAAA-MM-JJ.
          </p>
        )}
        {network?.niveaux_calcules && (
          <div className="grid gap-6 md:grid-cols-2">
            <StatBars rows={rows} barClass={(label) => LEVEL_BAR[label] ?? ""} emptyText="Aucun contact." />
            <section>
              <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Opportunités en cours
              </h3>
              {network.opportunites.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {network.opportunites.map((person) => (
                    <li key={`${person.nom}-${person.entreprise}`} className="py-1.5 text-sm">
                      <span className="font-medium">{person.nom}</span>
                      <span className="text-muted-foreground"> · {person.entreprise}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
        <AddressFinder />
      </CardContent>
    </Card>
  );
}
