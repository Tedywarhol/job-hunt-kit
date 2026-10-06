import { IconLayoutDashboard } from "@tabler/icons-react";
import { Link, useLocation } from "react-router";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const LABEL = "Tableau de bord";

/** Entry of the job-hunt dashboard, above the chat history in the sidebar. */
export function DashboardLink({ collapsed }: { collapsed: boolean }) {
  const active = useLocation().pathname === "/dashboard";
  const link = (
    <Link
      to="/dashboard"
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? LABEL : undefined}
      className={cn(
        "flex items-center text-sidebar-accent-foreground transition-colors hover:bg-sidebar-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        active && "bg-sidebar-accent",
        collapsed ? "size-10 justify-center rounded-md" : "mx-2 mb-1 h-10 gap-3 rounded-lg px-3 text-sm font-medium",
      )}
    >
      <IconLayoutDashboard className="size-4 shrink-0" strokeWidth={1.8} />
      <span className={collapsed ? "sr-only" : "truncate"}>{LABEL}</span>
    </Link>
  );

  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{LABEL}</TooltipContent>
    </Tooltip>
  );
}
