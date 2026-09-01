import type { RouteObject } from "react-router-dom";

import { AnalysisPage } from "../../features/analysis/analysis-page";
import { ConnectionWorkspace } from "../../features/connection/connection-workspace";
import { AppShell } from "../layout/app-shell";
import { NotFoundPage } from "./not-found-page";
import { ResultsPage } from "../../features/results/results-page";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <ConnectionWorkspace /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "results", element: <ResultsPage /> },
      {
        path: "erd",
        lazy: async () => {
          const { ErdPage } = await import("../../features/erd/erd-page");
          return { Component: ErdPage };
        },
      },
      {
        path: "exports",
        lazy: async () => {
          const { ExportsPage } = await import("../../features/exports/exports-page");
          return { Component: ExportsPage };
        },
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
