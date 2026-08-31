import { CheckCircle2 } from "lucide-react";

import type { ConnectionResponse } from "../../api/client";

type CapabilityChecksProps = {
  checks: ConnectionResponse["checks"];
  expiresInSeconds: number;
};

export function CapabilityChecks({ checks, expiresInSeconds }: CapabilityChecksProps) {
  return (
    <section className="border border-border bg-surface" aria-labelledby="capability-title">
      <div className="border-b border-border bg-surface-elevated px-4 py-2.5">
        <h2
          className="font-mono text-xs uppercase tracking-wider text-text-muted"
          id="capability-title"
        >
          Verified capabilities
        </h2>
      </div>
      <ul className="divide-y divide-border">
        {checks.map((check) => (
          <li className="flex items-center gap-2 px-4 py-2.5 text-sm" key={check.key}>
            <CheckCircle2 aria-hidden="true" className="size-4 text-success" />
            <span>{check.label}</span>
            <span className="ml-auto font-mono text-[10px] uppercase text-success">Available</span>
          </li>
        ))}
      </ul>
      <p className="border-t border-border px-4 py-2 text-xs text-text-muted">
        Session expires after {Math.round(expiresInSeconds / 60)} minutes of inactivity. ReliFinder
        operates with SELECT statements only; this does not prove the Oracle account itself lacks
        write privileges.
      </p>
    </section>
  );
}
