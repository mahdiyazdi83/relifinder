import { ArrowLeft, LockKeyhole } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

export function ResultsPlaceholderPage() {
  const location = useLocation();
  const runId = typeof location.state?.runId === "string" ? location.state.runId : null;
  return (
    <section className="mx-auto max-w-3xl px-5 py-10" aria-labelledby="results-title">
      <div className="border border-border bg-surface p-5">
        <LockKeyhole aria-hidden="true" className="size-5 text-accent" />
        <h1 className="mt-3 text-lg font-semibold text-text" id="results-title">
          Relationship results belong to Phase 4
        </h1>
        <p className="mt-2 text-sm leading-6 text-text-muted">
          {runId
            ? `Run ${runId.slice(0, 8)} completed. Detailed relationship browsing is intentionally not implemented yet.`
            : "Complete an analysis run before opening results."}
        </p>
        <Link
          className="mt-5 inline-flex items-center gap-2 text-sm text-accent hover:underline"
          to="/"
        >
          <ArrowLeft aria-hidden="true" className="size-4" /> Back to connection
        </Link>
      </div>
    </section>
  );
}
