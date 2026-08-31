import { Braces, Cable, ShieldCheck } from "lucide-react";

const foundations = [
  {
    icon: Cable,
    title: "Local API boundary",
    description: "The browser communicates through relative /api routes only.",
  },
  {
    icon: Braces,
    title: "Typed contracts",
    description: "Frontend API types are generated from FastAPI OpenAPI.",
  },
  {
    icon: ShieldCheck,
    title: "Core remains authoritative",
    description: "Inference and Oracle behavior stay in the existing Python core.",
  },
];

export function WorkspacePage() {
  return (
    <section aria-labelledby="workspace-title" className="mx-auto max-w-4xl px-8 py-8">
      <div className="border-b border-border pb-5">
        <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-text-muted">
          Workspace / Foundation
        </p>
        <h1 id="workspace-title" className="text-xl font-semibold tracking-tight text-text">
          ReliFinder workbench
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
          The local application foundation is ready. Connection and analysis workflows begin in
          later phases.
        </p>
      </div>

      <div className="mt-6 border border-border bg-surface" aria-label="Foundation capabilities">
        <div className="border-b border-border bg-surface-elevated px-4 py-2.5">
          <h2 className="font-mono text-xs font-medium uppercase tracking-wider text-text-muted">
            Architecture baseline
          </h2>
        </div>
        <ul className="divide-y divide-border">
          {foundations.map(({ icon: Icon, title, description }) => (
            <li className="grid gap-3 px-4 py-4 sm:grid-cols-[1.25rem_12rem_1fr]" key={title}>
              <Icon aria-hidden="true" className="mt-0.5 size-4 text-accent" strokeWidth={1.8} />
              <span className="text-sm font-medium text-text">{title}</span>
              <span className="text-sm leading-5 text-text-muted">{description}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
