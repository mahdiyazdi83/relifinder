import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "./providers/app-providers";
import { appRoutes } from "./router/routes";

function renderApp(path = "/") {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}

describe("ReliFinder application foundation", () => {
  it("renders the connection shell and backend health", async () => {
    renderApp();

    expect(screen.getByText("ReliFinder")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Secure Oracle connection" })).toBeInTheDocument();
    expect(await screen.findByText("Local Core: Healthy")).toBeInTheDocument();
  });

  it("provides a working not-found route", () => {
    renderApp("/missing");

    expect(screen.getByRole("heading", { name: "Workspace route not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return to workspace" })).toHaveAttribute("href", "/");
  });

  it("switches theme using an accessible button", async () => {
    const user = userEvent.setup();
    renderApp();

    const toggle = screen.getByRole("button", { name: "Switch to light theme" });
    await user.click(toggle);

    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });
});
