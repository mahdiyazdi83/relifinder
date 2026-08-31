import { Search, TableProperties, X } from "lucide-react";
import { useMemo, useState } from "react";

import type { SchemaSummary } from "../../api/client";
import { Button } from "../../components/ui/button";

const searchClass =
  "h-8 w-full border border-border bg-background pl-8 pr-3 text-sm text-text outline-none placeholder:text-text-muted/60 focus:border-focus focus:ring-1 focus:ring-focus";

type SchemaSelectorProps = {
  schemas: SchemaSummary[];
  selected: ReadonlySet<string>;
  onChange: (selected: Set<string>) => void;
};

export function SchemaSelector({ schemas, selected, onChange }: SchemaSelectorProps) {
  const [search, setSearch] = useState("");
  const [showSystem, setShowSystem] = useState(false);
  const visible = useMemo(() => {
    const query = search.trim().toLocaleUpperCase();
    return schemas.filter(
      (schema) =>
        (showSystem || !schema.oracle_maintained) &&
        (!query || schema.name.toLocaleUpperCase().includes(query)),
    );
  }, [schemas, search, showSystem]);
  const selectedSchemas = schemas.filter((schema) => selected.has(schema.name));
  const selectedTables = selectedSchemas.reduce((total, schema) => total + schema.table_count, 0);

  function toggle(name: string) {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onChange(next);
  }

  function selectVisible() {
    const next = new Set(selected);
    visible.forEach((schema) => next.add(schema.name));
    onChange(next);
  }

  return (
    <section aria-labelledby="schema-selector-title" className="border border-border bg-surface">
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface-elevated px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-text" id="schema-selector-title">
            Accessible schemas
          </h2>
          <p className="mt-0.5 text-xs text-text-muted">Metadata-visible tables only</p>
        </div>
        <div className="ml-auto font-mono text-xs text-text-muted" aria-live="polite">
          {selected.size} {selected.size === 1 ? "schema" : "schemas"} selected · {selectedTables}{" "}
          tables
        </div>
      </div>

      <div className="grid gap-3 border-b border-border p-3 sm:grid-cols-[minmax(12rem,1fr)_auto_auto]">
        <label className="relative">
          <span className="sr-only">Search schemas</span>
          <Search aria-hidden="true" className="absolute left-2.5 top-2 size-3.5 text-text-muted" />
          <input
            className={searchClass}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search schema names"
            type="search"
            value={search}
          />
        </label>
        <Button
          disabled={visible.length === 0}
          onClick={selectVisible}
          type="button"
          variant="ghost"
        >
          Select visible
        </Button>
        <Button
          disabled={selected.size === 0}
          onClick={() => onChange(new Set())}
          type="button"
          variant="ghost"
        >
          <X aria-hidden="true" className="size-3.5" /> Clear
        </Button>
      </div>

      <label className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-text-muted">
        <input
          checked={showSystem}
          className="accent-accent"
          onChange={(event) => setShowSystem(event.target.checked)}
          type="checkbox"
        />
        Show Oracle-maintained system schemas
      </label>

      {visible.length ? (
        <ul
          className="max-h-[22rem] divide-y divide-border overflow-y-auto"
          aria-label="Schema list"
        >
          {visible.map((schema) => (
            <li key={schema.name}>
              <label className="grid cursor-pointer grid-cols-[1.25rem_minmax(8rem,1fr)_6rem_6rem] items-center gap-3 px-4 py-2.5 text-sm hover:bg-surface-elevated focus-within:bg-surface-elevated max-sm:grid-cols-[1.25rem_1fr]">
                <input
                  checked={selected.has(schema.name)}
                  className="accent-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  onChange={() => toggle(schema.name)}
                  type="checkbox"
                />
                <span className="min-w-0 truncate font-mono text-xs font-medium text-text">
                  {schema.name}
                  {schema.oracle_maintained ? (
                    <span className="ml-2 border border-warning/50 px-1 py-0.5 text-[9px] text-warning">
                      SYSTEM
                    </span>
                  ) : null}
                </span>
                <span className="text-right font-mono text-[11px] text-text-muted max-sm:hidden">
                  {schema.table_count} tables
                </span>
                <span className="text-right font-mono text-[11px] text-text-muted max-sm:hidden">
                  {schema.column_count} columns
                </span>
              </label>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex items-center gap-3 px-4 py-8 text-sm text-text-muted">
          <TableProperties aria-hidden="true" className="size-4" />
          {schemas.length === 0
            ? "No schemas with accessible tables were found."
            : "No schemas match the current filters."}
        </div>
      )}
    </section>
  );
}
