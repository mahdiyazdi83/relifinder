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
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
