import { Database } from "lucide-react";
import { Outlet } from "react-router-dom";

import { HealthIndicator } from "../../features/system/health-indicator";
import { ThemeToggle } from "../../features/theme/theme-toggle";
import { WorkspaceRail } from "../../features/workspace/workspace-rail";

export function AppShell() {
  return (
    <div className="grid min-h-screen grid-rows-[3.25rem_1fr] bg-background text-text">
      <header
        className="relative z-30 flex items-center border-b border-border bg-surface/95 px-4 shadow-[0_1px_0_rgba(255,255,255,0.02)] backdrop-blur"
        aria-label="Application bar"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-8 place-items-center border border-accent/40 bg-accent/8 text-accent shadow-[inset_0_0_18px_var(--rf-accent-glow)]">
            <Database aria-hidden="true" className="size-4" strokeWidth={1.8} />
          </span>
          <span className="text-sm font-semibold tracking-[0.01em]">ReliFinder</span>
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

      <div className="grid min-h-0 grid-cols-[11.5rem_minmax(0,1fr)] max-lg:grid-cols-[3.75rem_minmax(0,1fr)]">
        <WorkspaceRail />
        <main className="min-w-0 overflow-auto bg-background [background-image:linear-gradient(var(--rf-grid)_1px,transparent_1px),linear-gradient(90deg,var(--rf-grid)_1px,transparent_1px)] [background-size:32px_32px">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
