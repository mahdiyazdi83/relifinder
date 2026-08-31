import type { RouteObject } from "react-router-dom";

import { AppShell } from "../layout/app-shell";
import { NotFoundPage } from "./not-found-page";
import { WorkspacePage } from "./workspace-page";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <WorkspacePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
