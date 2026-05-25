import type { ComponentType } from "react";

import { SopQualityPage } from "../features/sop/pages/SopQualityPage";

export type AppRoute = {
  Component: ComponentType;
  id: string;
  label: string;
  path: string;
};

export const appRoutes: AppRoute[] = [
  {
    Component: SopQualityPage,
    id: "sop-quality",
    label: "SOP Quality",
    path: "/",
  },
];

export function AppRoutes() {
  const RouteComponent = appRoutes[0].Component;

  return <RouteComponent />;
}
