import { useActionMutation } from "@agent-native/core/client/hooks";
import { IconFileTypePdf } from "@tabler/icons-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import type { DashboardData } from "../../../shared/dashboard-types";
import { SLUG_PATTERN } from "../../../shared/schemas";
import { ActionOutput } from "./ActionOutput";

type Folders = DashboardData["dossiers"];

export function FoldersCard({ folders }: { folders: Folders | undefined }) {
  const build = useActionMutation("build-application", { timeoutMs: 120000 });
  const [slug, setSlug] = useState("");
  const [profile, setProfile] = useState<"alternance" | "stage">("alternance");
  const valid = SLUG_PATTERN.test(slug);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid) build.mutate({ slug, profile });
  }

  return (
    <Card>
      <CardHeader className="space-y-1">
        <CardTitle className="text-base">Dossiers de candidature</CardTitle>
        <CardDescription>
          {folders ? `${folders.total} dossiers sous outputs/, les plus récents ci-dessous.` : "Chargement…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="divide-y divide-border">
          {folders?.recents.map((folder) => (
            <li key={folder.slug} className="flex items-center gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{folder.entreprise}</p>
                <button
                  type="button"
                  onClick={() => setSlug(folder.slug)}
                  className="truncate text-left text-xs text-muted-foreground hover:text-foreground"
                  title="Utiliser ce dossier ci-dessous"
                >
                  {folder.slug}
                </button>
              </div>
              {folder.pdf && <IconFileTypePdf className="size-4 shrink-0 text-muted-foreground" aria-label="PDF présents" />}
            </li>
          ))}
        </ul>

        <form onSubmit={submit} className="space-y-2 rounded-md border border-border p-3">
          <p className="text-sm font-medium">Régénérer le CV et la lettre</p>
          <div className="flex gap-2">
            <Input
              aria-label="Dossier"
              placeholder="acme-data-engineer"
              value={slug}
              onChange={(e) => setSlug(e.target.value.trim().toLowerCase())}
              list="dossiers-recents"
              className="min-w-0 flex-1"
            />
            <datalist id="dossiers-recents">
              {folders?.recents.map((folder) => <option key={folder.slug} value={folder.slug} />)}
            </datalist>
            <select
              aria-label="Type de profil"
              value={profile}
              onChange={(e) => setProfile(e.target.value as "alternance" | "stage")}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              <option value="alternance">Alternance</option>
              <option value="stage">Stage</option>
            </select>
            <Button type="submit" size="sm" disabled={!valid || build.isPending} className="h-9">
              {build.isPending ? "Génération…" : "Générer"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Le dossier doit déjà contenir cv-vars.json et lettre-vars.json : demandez-les à l'assistant (agent
            cv-tailor), puis générez les PDF ici. Rien n'est créé si les variables manquent.
          </p>
          {build.isError && <ActionOutput title="Échec" text={build.error.message} failed />}
          {build.data && (
            <ActionOutput
              title={build.data.success ? "PDF générés" : `Échec (code ${build.data.exitCode})`}
              text={[build.data.stdout, build.data.stderr].filter(Boolean).join("\n")}
              failed={!build.data.success}
            />
          )}
        </form>
      </CardContent>
    </Card>
  );
}
