import { Check, LockKeyhole } from "lucide-react";

const steps = ["Connection", "Schemas", "Analysis", "Results", "ERD"] as const;

type WorkflowStatusProps = {
  connected: boolean;
  schemaSelected: boolean;
};

export function WorkflowStatus({ connected, schemaSelected }: WorkflowStatusProps) {
  return (
    <ol
      className="grid grid-cols-5 border border-border bg-surface"
      aria-label="ReliFinder workflow"
    >
      {steps.map((step, index) => {
        const completed = (index === 0 && connected) || (index === 1 && schemaSelected);
        const current =
          (index === 0 && !connected) || (index === 1 && connected && !schemaSelected);
        const locked = index >= 2;
        return (
          <li
            aria-current={current ? "step" : undefined}
            className={`border-r border-border px-3 py-2 last:border-r-0 ${
              current ? "bg-surface-elevated" : ""
            }`}
            key={step}
          >
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-text-muted">
              {completed ? (
                <Check aria-hidden="true" className="size-3 text-success" />
              ) : locked ? (
                <LockKeyhole aria-hidden="true" className="size-3" />
              ) : (
                <span className={`size-1.5 ${current ? "bg-accent" : "bg-border"}`} />
              )}
              <span className="max-sm:sr-only">{index + 1}. </span>
              <span className="truncate max-sm:text-[8px]">{step}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
