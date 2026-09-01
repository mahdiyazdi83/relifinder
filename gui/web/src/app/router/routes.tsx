import type { RouteObject } from "react-router-dom";

import { AnalysisPage } from "../../features/analysis/analysis-page";
import { ConnectionWorkspace } from "../../features/connection/connection-workspace";
import { AppShell } from "../layout/app-shell";
import { NotFoundPage } from "./not-found-page";
import { ResultsPlaceholderPage } from "./results-placeholder-page";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <ConnectionWorkspace /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "results", element: <ResultsPlaceholderPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
