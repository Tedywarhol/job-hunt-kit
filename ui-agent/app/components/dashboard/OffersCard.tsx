import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { DashboardData } from "../../../shared/dashboard-types";

type Offers = DashboardData["offres"];
type Freshness = DashboardData["fraicheur"];

const FRESHNESS_LABELS: Array<[keyof Freshness, string]> = [
  ["today", "Aujourd'hui"],
  ["week", "7 jours"],
  ["month", "30 jours"],
  ["older", "Plus ancien"],
];

function isSafeLink(link: string): boolean {
  return /^https?:\/\//.test(link);
}

export function OffersCard({ offers, freshness }: { offers: Offers | undefined; freshness: Freshness | undefined }) {
  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Offres en attente</CardTitle>
        <CardDescription>
          {offers ? `${offers.en_attente} offre(s) détectées par le radar, les mieux notées d'abord.` : "Chargement…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {freshness && (
          <dl className="grid grid-cols-4 gap-2 text-center">
            {FRESHNESS_LABELS.map(([key, label]) => (
              <div key={key} className="rounded-md bg-muted/60 px-2 py-2">
                <dd className="text-lg font-semibold tabular-nums">{freshness[key]}</dd>
                <dt className="text-xs text-muted-foreground">{label}</dt>
              </div>
            ))}
          </dl>
        )}
        {offers && offers.meilleures.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune offre en attente : lancez un scan.</p>
        )}
        <ul className="divide-y divide-border">
          {offers?.meilleures.map((offer) => (
            <li key={`${offer.entreprise}-${offer.poste}`} className="flex items-center gap-3 py-2 text-sm">
              <span className="w-9 shrink-0 rounded-md bg-muted py-0.5 text-center text-xs font-medium tabular-nums">
                {offer.score}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{offer.entreprise}</p>
                <p className="truncate text-xs text-muted-foreground">{offer.poste}</p>
              </div>
              {isSafeLink(offer.lien) && (
                <a
                  href={offer.lien}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                >
                  Voir l'offre
                </a>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
