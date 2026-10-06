import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { NotionSnapshot } from "../../../shared/dashboard-types";
import { FUNNEL_ORDER, orderRows } from "./format";
import { StatBars } from "./StatBars";

interface FunnelCardProps {
  notion: NotionSnapshot | null | undefined;
  notionLoading: boolean;
  local: Record<string, number> | undefined;
}

function funnelBarClass(label: string): string {
  if (label === "Entretien" || label === "Offre reçue") return "bg-emerald-600";
  if (label === "Refusé" || label === "Écartée") return "bg-muted-foreground/40";
  return "bg-foreground/70";
}

export function FunnelCard({ notion, notionLoading, local }: FunnelCardProps) {
  // Notion holds the real status; the local file is only the fallback while it loads or when it is not configured.
  const useNotion = Boolean(notion);
  const counts = useNotion ? notion!.statuts : (local ?? {});
  const rows = orderRows(counts, FUNNEL_ORDER);

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Candidatures</CardTitle>
        <CardDescription>
          {useNotion
            ? `Statut réel dans Notion, ${notion!.total} lignes.`
            : notionLoading
              ? "Lecture de Notion en cours, en attendant : suivi local des envois."
              : "Notion indisponible ou non configuré : suivi local des envois."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <StatBars rows={rows} barClass={funnelBarClass} emptyText="Aucune candidature suivie." />
        {useNotion && notion!.relances_en_retard.length > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            {notion!.relances_en_retard.length} relance(s) en retard dans Notion.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
