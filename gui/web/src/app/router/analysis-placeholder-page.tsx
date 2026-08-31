import { ArrowLeft, LockKeyhole } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export function AnalysisPlaceholderPage() {
  const location = useLocation();
  const schemas = Array.isArray(location.state?.schemas)
    ? location.state.schemas.filter((value: unknown): value is string => typeof value === "string")
    : [];

  return (
    <section className="mx-auto max-w-3xl px-8 py-10" aria-labelledby="analysis-placeholder-title">
      <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">
        Workflow / Analysis
      </p>
      <div className="mt-4 border border-border bg-surface p-5">
        <LockKeyhole aria-hidden="true" className="size-5 text-accent" />
        <h1 className="mt-3 text-lg font-semibold text-text" id="analysis-placeholder-title">
          {schemas.length ? "Ready for analysis configuration" : "Schema selection required"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-text-muted">
          {schemas.length
            ? `${schemas.length} schema${schemas.length === 1 ? " is" : "s are"} ready. Analysis configuration belongs to Phase 3 and has not been implemented.`
            : "Return to the connection workflow and select at least one accessible schema."}
        </p>
        <Link
          className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          to="/"
        >
          <ArrowLeft aria-hidden="true" className="size-4" /> Back to connection
        </Link>
      </div>
    </section>
  );
}
