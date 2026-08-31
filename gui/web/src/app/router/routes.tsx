import type { RouteObject } from "react-router-dom";

import { ConnectionWorkspace } from "../../features/connection/connection-workspace";
import { AppShell } from "../layout/app-shell";
import { AnalysisPlaceholderPage } from "./analysis-placeholder-page";
import { NotFoundPage } from "./not-found-page";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <ConnectionWorkspace /> },
      { path: "analysis", element: <AnalysisPlaceholderPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
