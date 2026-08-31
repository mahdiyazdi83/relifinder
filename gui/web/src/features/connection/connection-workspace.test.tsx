import { delay, http, HttpResponse } from "msw";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../../app/providers/app-providers";
import { appRoutes } from "../../app/router/routes";
import { server } from "../../test/mocks/server";

const fakePassword = "fake-browser-password-9Z!";
const schemas = [
  { name: "APP", table_count: 12, column_count: 84, oracle_maintained: false },
  { name: "CORE", table_count: 7, column_count: 39, oracle_maintained: false },
  { name: "SYS", table_count: 120, column_count: 900, oracle_maintained: true },
];

function installSuccessfulApi(connectionId = "opaque-session-id-12345678901234567890") {
  server.use(
    http.post("/api/connections", () =>
      HttpResponse.json(
        {
          connection_id: connectionId,
          status: "connected",
          expires_in_seconds: 900,
          checks: [
            { key: "oracle_connection", label: "Oracle connection", status: "available" },
            { key: "metadata_visibility", label: "Metadata visibility", status: "available" },
            { key: "schema_discovery", label: "Schema discovery", status: "available" },
          ],
        },
        { status: 201 },
      ),
    ),
    http.get("/api/connections/:connectionId/schemas", ({ params }) =>
      HttpResponse.json({ connection_id: params.connectionId, schemas }),
    ),
    http.delete("/api/connections/:connectionId", () => new HttpResponse(null, { status: 204 })),
  );
}

function renderApp() {
  return render(
    <AppProviders>
      <RouterProvider router={createMemoryRouter(appRoutes)} />
    </AppProviders>,
  );
}

async function fillConnectionForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Host"), "db.example.invalid");
  await user.type(screen.getByLabelText("Service name"), "FAKE_SERVICE");
  await user.type(screen.getByLabelText("Username"), "FAKE_USER");
  await user.type(screen.getByLabelText("Password"), fakePassword);
}

async function connect(user: ReturnType<typeof userEvent.setup>) {
  await fillConnectionForm(user);
  await user.click(screen.getByRole("button", { name: "Test connection" }));
  await screen.findByRole("heading", { name: "Accessible schemas" });
}

describe("secure connection and schema workflow", () => {
  it("validates required fields and the Oracle port", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.clear(screen.getByLabelText("Port"));
    await user.type(screen.getByLabelText("Port"), "70000");
    await user.click(screen.getByRole("button", { name: "Test connection" }));

    expect(await screen.findByText("Host is required")).toBeInTheDocument();
    expect(screen.getByText("Service name is required")).toBeInTheDocument();
    expect(screen.getByText("Username is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(screen.getByText("Port cannot exceed 65535")).toBeInTheDocument();
  });

  it("disables duplicate submission while connection verification is running", async () => {
    server.use(
      http.post("/api/connections", async () => {
        await delay(200);
        return HttpResponse.json({}, { status: 500 });
      }),
    );
    const user = userEvent.setup();
    renderApp();
    await fillConnectionForm(user);

    await user.click(screen.getByRole("button", { name: "Test connection" }));

    expect(screen.getByRole("button", { name: "Testing connection…" })).toBeDisabled();
  });

  it("renders capabilities and schemas without persisting the password", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    renderApp();
    await connect(user);

    expect(screen.getByText("Metadata visibility")).toBeInTheDocument();
    expect(screen.getByText("APP")).toBeInTheDocument();
    expect(screen.getByText("CORE")).toBeInTheDocument();
    expect(screen.queryByText("SYS")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveValue("");
    const localValues = Array.from({ length: window.localStorage.length }, (_, index) =>
      window.localStorage.getItem(window.localStorage.key(index) ?? ""),
    ).join(" ");
    const sessionValues = Array.from({ length: window.sessionStorage.length }, (_, index) =>
      window.sessionStorage.getItem(window.sessionStorage.key(index) ?? ""),
    ).join(" ");
    expect(localValues).not.toContain(fakePassword);
    expect(sessionValues).not.toContain(fakePassword);
  });

  it("shows only the sanitized backend connection error", async () => {
    server.use(
      http.post("/api/connections", () =>
        HttpResponse.json(
          {
            error: {
              code: "AUTHENTICATION_FAILED",
              message: "Oracle rejected the supplied username or password.",
            },
          },
          { status: 401 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderApp();
    await fillConnectionForm(user);
    await user.click(screen.getByRole("button", { name: "Test connection" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Oracle rejected the supplied username or password.",
    );
    expect(document.body).not.toHaveTextContent(fakePassword);
  });

  it("searches, selects, selects all visible, clears, and enables Continue", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    renderApp();
    await connect(user);

    const selector = screen.getByRole("region", { name: "Accessible schemas" });
    expect(within(selector).getByText("0 schemas selected · 0 tables")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continue/ })).toBeDisabled();

    await user.type(screen.getByRole("searchbox", { name: "Search schemas" }), "core");
    expect(within(selector).queryByText("APP")).not.toBeInTheDocument();
    await user.click(within(selector).getByRole("checkbox", { name: /CORE/ }));
    expect(within(selector).getByText("1 schema selected · 7 tables")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continue/ })).toBeEnabled();

    await user.clear(screen.getByRole("searchbox", { name: "Search schemas" }));
    await user.click(within(selector).getByRole("button", { name: "Select visible" }));
    expect(within(selector).getByText("2 schemas selected · 19 tables")).toBeInTheDocument();
    await user.click(within(selector).getByRole("button", { name: /Clear/ }));
    expect(within(selector).getByText("0 schemas selected · 0 tables")).toBeInTheDocument();
  });

  it("can reveal system schemas explicitly", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    renderApp();
    await connect(user);

    await user.click(
      screen.getByRole("checkbox", { name: "Show Oracle-maintained system schemas" }),
    );

    expect(screen.getByText("SYS")).toBeInTheDocument();
    expect(screen.getByText("SYSTEM")).toBeInTheDocument();
  });

  it("disconnects and clears connection and selection state", async () => {
    installSuccessfulApi();
    const user = userEvent.setup();
    renderApp();
    await connect(user);
    await user.click(screen.getByRole("checkbox", { name: /APP/ }));

    await user.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(await screen.findByText("No verified connection")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Accessible schemas" })).not.toBeInTheDocument();
  });

  it("resets schema selection after a successful replacement connection", async () => {
    let requestCount = 0;
    server.use(
      http.post("/api/connections", () => {
        requestCount += 1;
        return HttpResponse.json(
          {
            connection_id: `opaque-session-${requestCount}-12345678901234567890`,
            status: "connected",
            expires_in_seconds: 900,
            checks: [
              { key: "oracle_connection", label: "Oracle connection", status: "available" },
              { key: "metadata_visibility", label: "Metadata visibility", status: "available" },
              { key: "schema_discovery", label: "Schema discovery", status: "available" },
            ],
          },
          { status: 201 },
        );
      }),
      http.get("/api/connections/:connectionId/schemas", ({ params }) =>
        HttpResponse.json({ connection_id: params.connectionId, schemas }),
      ),
    );
    const user = userEvent.setup();
    renderApp();
    await connect(user);
    await user.click(screen.getByRole("checkbox", { name: /APP/ }));
    expect(screen.getByText("1 schema selected · 12 tables")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Password"), fakePassword);
    await user.click(screen.getByRole("button", { name: "Replace connection" }));

    expect(await screen.findByText("0 schemas selected · 0 tables")).toBeInTheDocument();
    expect(requestCount).toBe(2);
  });
});
