import { useActionMutation } from "@agent-native/core/client/hooks";
import { IconChecklist, IconRadar2, IconSearch } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { ActionOutput } from "./ActionOutput";

interface Report {
  title: string;
  text: string;
  failed: boolean;
}

function toReport(title: string, data: { success: boolean; report?: string; stdout?: string; stderr?: string }): Report {
  return { title, text: data.report ?? data.stdout ?? data.stderr ?? "", failed: !data.success };
}

export function ToolsCard({ onScanned }: { onScanned: () => void }) {
  const scan = useActionMutation("scan-jobs", { timeoutMs: 180000, onSuccess: onScanned });
  const consistency = useActionMutation("check-consistency", { timeoutMs: 120000 });
  const coverage = useActionMutation("check-ats-coverage", { timeoutMs: 120000 });

  const reports: Report[] = [];
  if (scan.data) reports.push(toReport("Scan des offres (ATS)", scan.data));
  if (consistency.data) reports.push(toReport("Contrôle de cohérence", consistency.data));
  if (coverage.data) reports.push(toReport("Couverture des mots-clés ATS", coverage.data));
  const errors = [scan.error, consistency.error, coverage.error].filter((e): e is Error => Boolean(e));

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Outils</CardTitle>
        <CardDescription>Contrôles en lecture seule, sauf le scan qui met à jour la file des offres.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={scan.isPending} onClick={() => scan.mutate({ source: "ats" })}>
            <IconRadar2 className="size-4" />
            {scan.isPending ? "Scan en cours…" : "Scanner les offres"}
          </Button>
          <Button size="sm" variant="outline" disabled={consistency.isPending} onClick={() => consistency.mutate({})}>
            <IconChecklist className="size-4" />
            {consistency.isPending ? "Contrôle…" : "Contrôle de cohérence"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={coverage.isPending}
            onClick={() => coverage.mutate({ all: true })}
          >
            <IconSearch className="size-4" />
            {coverage.isPending ? "Analyse…" : "Couverture ATS"}
          </Button>
        </div>
        {errors.map((error) => (
          <ActionOutput key={error.message} title="Échec" text={error.message} failed />
        ))}
        {reports.map((report) => (
          <ActionOutput key={report.title} title={report.title} text={report.text} failed={report.failed} />
        ))}
      </CardContent>
    </Card>
  );
}
