import { Navigate } from "react-router";

import { APP_TITLE } from "@/lib/app-config";

export function meta() {
  return [{ title: `${APP_TITLE} - Tableau de bord de recherche d'alternance` }];
}

/** Local single-user tool: no marketing page, the dashboard is the home. */
export default function IndexRoute() {
  return <Navigate to="/dashboard" replace />;
}
