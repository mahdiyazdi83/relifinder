import { RotateCcw, Search } from "lucide-react";

import type { RelationshipListItem } from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  defaultRelationshipFilters,
  hasActiveFilters,
  relationshipFilterOptions,
  type RelationshipFilters,
} from "./relationship-filters";

export function RelationshipToolbar({
  relationships,
  filters,
  shown,
  onChange,
}: {
  relationships: RelationshipListItem[];
  filters: RelationshipFilters;
  shown: number;
  onChange: (filters: RelationshipFilters) => void;
}) {
  const options = relationshipFilterOptions(relationships);
  const active = hasActiveFilters(filters);
  const update = <Key extends keyof RelationshipFilters>(
    key: Key,
    value: RelationshipFilters[Key],
  ) => onChange({ ...filters, [key]: value });

  return (
    <section className="border-b border-border bg-surface" aria-label="Relationship filters">
      <div className="grid gap-2 p-3 lg:grid-cols-[minmax(14rem,1.4fr)_repeat(3,minmax(8rem,0.7fr))]">
        <label className="relative">
          <span className="sr-only">Search relationships</span>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-text-muted"
          />
          <input
            className="h-9 w-full border border-border bg-background pl-8 pr-2 text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            onChange={(event) => update("search", event.target.value)}
            placeholder="Search schema, table, or column"
            type="search"
            value={filters.search}
          />
        </label>
        <FilterSelect
          label="Source schema"
          onChange={(value) => update("sourceSchema", value)}
          options={options.sourceSchemas}
          value={filters.sourceSchema}
        />
        <FilterSelect
          label="Target schema"
          onChange={(value) => update("targetSchema", value)}
          options={options.targetSchemas}
          value={filters.targetSchema}
        />
        <label className="flex h-9 items-center gap-2 border border-border bg-background px-2 text-xs text-text-muted">
          Min confidence
          <input
            aria-label="Minimum confidence"
            className="min-w-0 flex-1 bg-transparent text-right font-mono text-sm text-text outline-none"
            max={100}
            min={0}
            onChange={(event) => update("minConfidence", Number(event.target.value))}
            type="number"
            value={filters.minConfidence}
          />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2">
        <FilterSelect
          label="Confidence label"
          onChange={(value) => update("confidenceLabel", value)}
          options={options.confidenceLabels}
          value={filters.confidenceLabel}
        />
        <FilterSelect
          label="Cardinality"
          onChange={(value) => update("cardinality", value)}
          options={options.cardinalities}
          value={filters.cardinality}
        />
        <FilterSelect
          label="Validation"
          onChange={(value) => update("validationStatus", value)}
          options={options.validationStatuses}
          value={filters.validationStatus}
        />
        <FilterSelect
          label="Target key"
          onChange={(value) => update("targetKeyType", value)}
          options={options.targetKeyTypes}
          value={filters.targetKeyType}
        />
        <label className="flex items-center gap-2 px-1 text-xs text-text-muted">
          <input
            checked={filters.crossSchemaOnly}
            className="size-3.5 accent-[var(--rf-accent)]"
            onChange={(event) => update("crossSchemaOnly", event.target.checked)}
            type="checkbox"
          />
          Cross-schema only
        </label>
        <span className="ml-auto font-mono text-[11px] text-text-muted" role="status">
          Showing {shown.toLocaleString()} of {relationships.length.toLocaleString()} relationships
        </span>
        {active ? (
          <Button
            aria-label="Clear filters"
            onClick={() =>
              onChange({
                ...defaultRelationshipFilters,
                sortKey: filters.sortKey,
                sortDirection: filters.sortDirection,
              })
            }
            type="button"
            variant="ghost"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            Clear filters
          </Button>
        ) : null}
      </div>
    </section>
  );
}

function FilterSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-xs text-text-muted">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        className="h-9 max-w-52 border border-border bg-background px-2 text-xs text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">All {label.toLocaleLowerCase()}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}
