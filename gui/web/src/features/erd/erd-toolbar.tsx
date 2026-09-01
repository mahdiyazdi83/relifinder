import { Focus, LocateFixed, Network, RotateCcw } from "lucide-react";

import { Button } from "../../components/ui/button";
import type { ErdFilters } from "./erd-types";

export function ErdToolbar({
  filters,
  availableSchemas,
  nodeCount,
  edgeCount,
  focusActive,
  layoutBusy,
  onChange,
  onFitView,
  onAutoLayout,
  onExitFocus,
}: {
  filters: ErdFilters;
  availableSchemas: string[];
  nodeCount: number;
  edgeCount: number;
  focusActive: boolean;
  layoutBusy: boolean;
  onChange: (filters: ErdFilters) => void;
  onFitView: () => void;
  onAutoLayout: () => void;
  onExitFocus: () => void;
}) {
  function toggleSchema(schema: string) {
    const selected = new Set(filters.schemas);
    if (selected.has(schema)) selected.delete(schema);
    else selected.add(schema);
    onChange({ ...filters, schemas: [...selected].sort() });
  }

  return (
    <section aria-label="ERD controls" className="border-b border-border bg-surface px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-8 items-center gap-2 border border-border bg-background px-2 text-xs text-text-muted">
          Confidence ≥
          <input
            aria-label="ERD minimum confidence"
            className="w-14 bg-transparent text-right font-mono text-text outline-none"
            max={100}
            min={0}
            onChange={(event) =>
              onChange({
                ...filters,
                minConfidence: Math.min(100, Math.max(0, Number(event.target.value))),
              })
            }
            type="number"
            value={filters.minConfidence}
          />
        </label>
        <label>
          <span className="sr-only">ERD validation status</span>
          <select
            aria-label="ERD validation status"
            className="h-8 border border-border bg-background px-2 text-xs text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            onChange={(event) => onChange({ ...filters, validationStatus: event.target.value })}
            value={filters.validationStatus}
          >
            <option value="">All validation states</option>
            <option value="VALIDATED">VALIDATED</option>
            <option value="NOT_RUN">NOT_RUN</option>
            <option value="SKIPPED">SKIPPED</option>
            <option value="FAILED">FAILED</option>
          </select>
        </label>
        <label className="flex h-8 items-center gap-2 border border-border bg-background px-2 text-xs text-text-muted">
          <input
            checked={filters.crossSchemaOnly}
            className="size-3.5 accent-[var(--rf-accent)]"
            onChange={(event) => onChange({ ...filters, crossSchemaOnly: event.target.checked })}
            type="checkbox"
          />
          Cross-schema only
        </label>
        <span className="font-mono text-[10px] text-text-muted" role="status">
          {nodeCount.toLocaleString()} tables · {edgeCount.toLocaleString()} relationships
        </span>
        <div className="ml-auto flex items-center gap-1">
          {focusActive ? (
            <Button onClick={onExitFocus} type="button" variant="ghost">
              <Focus aria-hidden="true" className="size-3.5" /> Exit Focus
            </Button>
          ) : null}
          <Button aria-label="Fit ERD view" onClick={onFitView} type="button" variant="ghost">
            <LocateFixed aria-hidden="true" className="size-3.5" /> Fit view
          </Button>
          <Button disabled={layoutBusy} onClick={onAutoLayout} type="button" variant="ghost">
            <Network aria-hidden="true" className="size-3.5" />
            {layoutBusy ? "Laying out…" : "Auto Layout"}
          </Button>
        </div>
      </div>
      <details className="relative mt-2 text-xs text-text-muted">
        <summary className="w-fit cursor-pointer select-none font-mono text-[10px] uppercase tracking-wider hover:text-text">
          Schemas {filters.schemas.length}/{availableSchemas.length}
        </summary>
        <fieldset className="mt-2 flex max-h-24 flex-wrap gap-x-4 gap-y-2 overflow-auto border-t border-border pt-2">
          <legend className="sr-only">Schema filter</legend>
          <button
            className="flex items-center gap-1 text-accent hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            onClick={() => onChange({ ...filters, schemas: [...availableSchemas] })}
            type="button"
          >
            <RotateCcw aria-hidden="true" className="size-3" /> All schemas
          </button>
          {availableSchemas.map((schema) => (
            <label className="flex items-center gap-1.5 font-mono" key={schema}>
              <input
                checked={filters.schemas.includes(schema)}
                className="size-3.5 accent-[var(--rf-accent)]"
                onChange={() => toggleSchema(schema)}
                type="checkbox"
              />
              {schema}
            </label>
          ))}
        </fieldset>
      </details>
    </section>
  );
}
