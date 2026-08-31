import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { AppProviders } from "./app/providers/app-providers";
import { appRouter } from "./app/router/router";
import "./styles/index.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("ReliFinder root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <RouterProvider router={appRouter} />
    </AppProviders>
  </StrictMode>,
);
