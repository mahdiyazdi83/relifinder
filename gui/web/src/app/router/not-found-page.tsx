import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-3xl px-8 py-12" aria-labelledby="not-found-title">
      <p className="font-mono text-xs text-danger">404 / ROUTE_NOT_FOUND</p>
      <h1 id="not-found-title" className="mt-3 text-xl font-semibold text-text">
        Workspace route not found
      </h1>
      <p className="mt-2 text-sm text-text-muted">This route is not part of the local workbench.</p>
      <Link
        className="mt-5 inline-flex text-sm font-medium text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        to="/"
      >
        Return to workspace
      </Link>
    </section>
  );
}
