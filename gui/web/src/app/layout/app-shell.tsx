import { Database, PanelLeftClose } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { HealthIndicator } from "../../features/system/health-indicator";
import { ThemeToggle } from "../../features/theme/theme-toggle";

export function AppShell() {
  return (
    <div className="grid min-h-screen grid-rows-[3rem_1fr] bg-background text-text">
      <header
        className="flex items-center border-b border-border bg-surface px-4"
        aria-label="Application bar"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-7 place-items-center border border-border bg-surface-elevated text-accent">
            <Database aria-hidden="true" className="size-4" strokeWidth={1.8} />
          </span>
          <span className="text-sm font-semibold tracking-tight">ReliFinder</span>
          <span className="hidden border-l border-border pl-2 font-mono text-[10px] uppercase tracking-widest text-text-muted sm:inline">
            Local workbench
          </span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <HealthIndicator />
          <span className="h-5 w-px bg-border" aria-hidden="true" />
          <ThemeToggle />
        </div>
      </header>

      <div className="grid min-h-0 grid-cols-[12.5rem_1fr] max-sm:grid-cols-[3.25rem_1fr]">
        <aside className="border-r border-border bg-surface" aria-label="Primary navigation">
          <div className="flex h-10 items-center border-b border-border px-3 text-text-muted max-sm:justify-center">
            <PanelLeftClose aria-hidden="true" className="size-3.5" />
            <span className="ml-2 font-mono text-[10px] uppercase tracking-widest max-sm:hidden">
              Navigation
            </span>
          </div>
          <nav className="p-2">
            <NavLink
              className={({ isActive }) =>
                `flex items-center gap-2 border-l-2 px-2 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                  isActive
                    ? "border-accent bg-surface-elevated text-text"
                    : "border-transparent text-text-muted hover:bg-surface-elevated hover:text-text"
                }`
              }
              end
              to="/"
            >
              <Database aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={1.8} />
              <span className="max-sm:sr-only">Workspace</span>
            </NavLink>
          </nav>
        </aside>

        <main className="min-w-0 overflow-auto bg-background">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
