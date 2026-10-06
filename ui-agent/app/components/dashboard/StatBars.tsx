import { cn } from "@/lib/utils";

import { barWidth, type Row } from "./format";

interface StatBarsProps {
  rows: Row[];
  /** Tailwind class of the bar of a given label, to colour the warm and the cold ends differently. */
  barClass?: (label: string) => string;
  emptyText: string;
}

/** Horizontal bars with the count at the end of each row. Plain markup: no chart library. */
export function StatBars({ rows, barClass, emptyText }: StatBarsProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }
  const max = Math.max(...rows.map((row) => row.value));
  return (
    <ul className="space-y-2">
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[8.5rem_1fr_2.5rem] items-center gap-3 text-sm">
          <span className="truncate text-foreground" title={row.label}>
            {row.label}
          </span>
          <span className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <span
              className={cn("block h-full rounded-full", barClass?.(row.label) ?? "bg-foreground/70")}
              style={{ width: barWidth(row.value, max) }}
            />
          </span>
          <span className="text-right tabular-nums text-muted-foreground">{row.value}</span>
        </li>
      ))}
    </ul>
  );
}
