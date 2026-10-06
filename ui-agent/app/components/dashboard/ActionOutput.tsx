import { cn } from "@/lib/utils";

interface ActionOutputProps {
  title: string;
  text: string;
  failed?: boolean;
}

/** Text report of a script, shown as is: the scripts already format it for a human. */
export function ActionOutput({ title, text, failed }: ActionOutputProps) {
  return (
    <div className="mt-3 rounded-md border border-border bg-muted/40">
      <p
        className={cn(
          "border-b border-border px-3 py-1.5 text-xs font-medium",
          failed ? "text-destructive" : "text-muted-foreground",
        )}
      >
        {title}
      </p>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap px-3 py-2 text-xs leading-relaxed">
        {text.trim() || "(aucune sortie)"}
      </pre>
    </div>
  );
}
