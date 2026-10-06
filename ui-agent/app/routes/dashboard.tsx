import { useActionQuery } from "@agent-native/core/client/hooks";
import { IconRefresh } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { APP_TITLE } from "@/lib/app-config";

import type { DashboardData } from "../../shared/dashboard-types";
import { FoldersCard } from "@/components/dashboard/FoldersCard";
import { FunnelCard } from "@/components/dashboard/FunnelCard";
import { NetworkCard } from "@/components/dashboard/NetworkCard";
import { OffersCard } from "@/components/dashboard/OffersCard";
import { TodayCard } from "@/components/dashboard/TodayCard";
import { ToolsCard } from "@/components/dashboard/ToolsCard";

export function meta() {
  return [{ title: `Tableau de bord - ${APP_TITLE}` }];
}

/** get-dashboard-stats also has a text format: the screen always asks for the JSON one. */
function asDashboard(data: unknown): DashboardData | undefined {
  return data && typeof data === "object" && "relances" in data ? (data as DashboardData) : undefined;
}

export default function DashboardRoute() {
  // Two queries: the local data shows at once, the real Notion statuses arrive a few seconds later.
  const local = useActionQuery("get-dashboard-stats", { format: "json", notion: false });
  const real = useActionQuery("get-dashboard-stats", { format: "json", notion: true }, { staleTime: 60_000 });
  const data = asDashboard(local.data);
  const withNotion = asDashboard(real.data);

  function refresh() {
    void local.refetch();
    void real.refetch();
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 lg:px-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tableau de bord</h1>
          <p className="text-sm text-muted-foreground">
            {data ? `Données du ${data.genere_le}. Le kit prépare, vous décidez : rien ne part sans vous.` : "Chargement…"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={local.isFetching}>
          <IconRefresh className={local.isFetching ? "size-4 animate-spin" : "size-4"} />
          Actualiser
        </Button>
      </header>

      {local.isError && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Impossible de lire les données du kit : {local.error.message}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <TodayCard relances={data?.relances} />
        <FunnelCard
          notion={withNotion ? withNotion.notion : real.isError ? null : undefined}
          notionLoading={real.isLoading}
          local={data?.statuts_locaux}
        />
        <OffersCard offers={data?.offres} freshness={data?.fraicheur} />
        <NetworkCard network={data?.reseau} loading={local.isLoading} />
        <FoldersCard folders={data?.dossiers} />
        <ToolsCard onScanned={refresh} />
      </div>
    </div>
  );
}
