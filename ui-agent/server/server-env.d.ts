/// <reference types="vite/client" />

declare module "virtual:react-router/server-build" {
  export const routes: Record<string, unknown>;
  export const entry: { module: unknown };
}

declare module "*actions-registry.js" {
  export const actions: Record<string, unknown>;
  export default actions;
}
