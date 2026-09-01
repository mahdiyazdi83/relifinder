import { Focus, X } from "lucide-react";

import type { ErdGraphTable } from "../../api/client";
import { Button } from "../../components/ui/button";

export function ErdTableInspector({
  table,
  incomingCount,
  outgoingCount,
  focused,
  onFocus,
  onClose,
}: {
  table: ErdGraphTable;
  incomingCount: number;
  outgoingCount: number;
  focused: boolean;
  onFocus: () => void;
  onClose: () => void;
}) {
  return (
    <aside
      aria-label="Table inspector"
      className="min-h-0 overflow-auto border-l border-border bg-surface max-xl:border-l-0 max-xl:border-t"
    >
      <header className="flex h-10 items-center border-b border-border bg-surface-elevated px-3">
        <h2 className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
          Table inspector
        </h2>
        <Button
          aria-label="Close table inspector"
          className="ml-auto"
          onClick={onClose}
          size="icon"
          type="button"
          variant="ghost"
        >
          <X aria-hidden="true" className="size-4" />
        </Button>
      </header>
      <div className="p-4">
        <p className="font-mono text-[11px] text-text-muted">{table.schema_name}</p>
        <h3 className="mt-1 font-mono text-base font-semibold text-text">{table.table_name}</h3>
        <dl className="mt-4 divide-y divide-border text-xs">
          <Metric
            label="Estimated rows"
            value={table.estimated_rows?.toLocaleString() ?? "Unavailable"}
          />
          <Metric label="Columns" value={table.columns.length.toLocaleString()} />
          <Metric label="Primary key columns" value={count(table, "primary_key")} />
          <Metric label="Unique key columns" value={count(table, "unique_key")} />
          <Metric label="Incoming relationships" value={incomingCount.toLocaleString()} />
          <Metric label="Outgoing relationships" value={outgoingCount.toLocaleString()} />
        </dl>
        <Button className="mt-4 w-full" disabled={focused} onClick={onFocus} type="button">
          <Focus aria-hidden="true" className="size-4" />
          {focused ? "Table focused" : "Focus table (1 hop)"}
        </Button>
        <section className="mt-5 border-t border-border pt-4">
          <h4 className="font-mono text-[10px] uppercase tracking-widest text-text-muted">
            Columns
          </h4>
          <div className="mt-2 max-h-80 overflow-auto border border-border">
            {table.columns.map((column) => (
              <div
                className="grid grid-cols-[2.6rem_minmax(0,1fr)_5rem] gap-1 border-b border-border/70 px-2 py-1.5 font-mono text-[10px] last:border-b-0"
                key={column.name}
              >
                <span className="font-semibold text-accent">
                  {column.primary_key
                    ? "PK"
                    : column.unique_key
                      ? "UK"
                      : column.composite_key
                        ? "CK"
                        : ""}
                </span>
                <span className="truncate text-text">{column.name}</span>
                <span className="truncate text-right text-text-muted">{column.datatype}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 py-2">
      <dt className="text-text-muted">{label}</dt>
      <dd className="font-mono text-text">{value}</dd>
    </div>
  );
}

function count(table: ErdGraphTable, key: "primary_key" | "unique_key"): string {
  return table.columns.filter((column) => column[key]).length.toLocaleString();
}
