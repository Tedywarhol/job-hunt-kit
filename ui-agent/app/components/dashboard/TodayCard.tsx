import { useActionMutation } from "@agent-native/core/client/hooks";
import { IconMailForward } from "@tabler/icons-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { FollowupDue } from "../../../shared/dashboard-types";
import { ActionOutput } from "./ActionOutput";
import { groupRelances, relanceLabel, relanceTone, type Tone } from "./format";

const TONE_CLASS: Record<Tone, string> = {
  late: "bg-destructive/10 text-destructive",
  today: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  soon: "bg-muted text-muted-foreground",
};

function Group({ title, items }: { title: string; items: FollowupDue[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="divide-y divide-border">
        {items.map((item) => (
          <li key={`${item.entreprise}-${item.poste}-${item.echeance}`} className="flex items-center gap-3 py-2 text-sm">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{item.entreprise}</p>
              <p className="truncate text-xs text-muted-foreground">{item.poste}</p>
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">{item.etape_suivante}</span>
            <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-xs", TONE_CLASS[relanceTone(item.jours)])}>
              {relanceLabel(item.jours)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TodayCard({ relances }: { relances: FollowupDue[] | undefined }) {
  const plan = useActionMutation("plan-followups", { timeoutMs: 180000 });
  const grouped = groupRelances(relances ?? []);

  return (
    <Card className="md:col-span-2">
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div>
          <CardTitle className="text-base">À faire</CardTitle>
          <CardDescription>
            Relances dues d'après les dates de state/outreach.json. Une réponse a pu arriver sans y être notée.
          </CardDescription>
        </div>
        <Button size="sm" variant="outline" onClick={() => plan.mutate({})} disabled={plan.isPending}>
          <IconMailForward className="size-4" />
          {plan.isPending ? "Vérification Gmail…" : "Vérifier dans Gmail"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {relances === undefined ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : relances.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune relance due dans les 3 prochains jours.</p>
        ) : (
          <>
            <Group title="En retard" items={grouped.late} />
            <Group title="Aujourd'hui" items={grouped.today} />
            <Group title="Bientôt" items={grouped.soon} />
          </>
        )}
        {plan.isError && <ActionOutput title="Échec de la vérification" text={plan.error.message} failed />}
        {plan.data && (
          <ActionOutput
            title="Simulation des relances (aucun brouillon créé)"
            text={plan.data.report || plan.data.stderr || ""}
            failed={!plan.data.success}
          />
        )}
      </CardContent>
    </Card>
  );
}
