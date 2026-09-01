import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";

import type { RelationshipListItem } from "../../api/client";
import { Button } from "../../components/ui/button";
import type { RelationshipFilters, RelationshipSortKey } from "./relationship-filters";

const PAGE_SIZE = 100;

export function RelationshipTable({
  relationships,
  selectedId,
  filters,
  page,
  onPageChange,
  onFiltersChange,
  onSelect,
}: {
  relationships: RelationshipListItem[];
  selectedId: string | null;
  filters: RelationshipFilters;
  page: number;
  onPageChange: (page: number) => void;
  onFiltersChange: (filters: RelationshipFilters) => void;
  onSelect: (relationshipId: string) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(relationships.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const visible = relationships.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  function sort(key: RelationshipSortKey) {
    onFiltersChange({
      ...filters,
      sortKey: key,
      sortDirection: filters.sortKey === key && filters.sortDirection === "desc" ? "asc" : "desc",
    });
  }

  return (
    <div className="min-w-0">
      <div className="overflow-auto">
        <table className="w-full min-w-[48rem] border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-surface-elevated text-text-muted">
            <tr>
              <SortableHeader
                active={filters.sortKey === "source"}
                direction={filters.sortDirection}
                label="Source"
                onClick={() => sort("source")}
              />
              <SortableHeader
                active={filters.sortKey === "target"}
                direction={filters.sortDirection}
                label="Target"
                onClick={() => sort("target")}
              />
              <SortableHeader
                active={filters.sortKey === "confidence"}
                direction={filters.sortDirection}
                label="Confidence"
                onClick={() => sort("confidence")}
              />
              <SortableHeader
                active={filters.sortKey === "cardinality"}
                direction={filters.sortDirection}
                label="Cardinality"
                onClick={() => sort("cardinality")}
              />
              <SortableHeader
                active={filters.sortKey === "validation"}
                direction={filters.sortDirection}
                label="Validation"
                onClick={() => sort("validation")}
              />
              <th className="border-b border-border px-3 py-2 font-medium">Match</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => {
              const selected = item.id === selectedId;
              return (
                <tr
                  aria-selected={selected}
                  className={`cursor-pointer border-b border-border/70 outline-none transition-colors hover:bg-surface-elevated focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus ${
                    selected ? "bg-accent/10" : "bg-surface"
                  }`}
                  key={item.id}
                  onClick={() => onSelect(item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(item.id);
                    }
                  }}
                  tabIndex={0}
                >
                  <td className="px-3 py-2.5">
                    <Endpoint endpoint={item.source} />
                  </td>
                  <td className="px-3 py-2.5">
                    <Endpoint endpoint={item.target} />
                    {item.cross_schema ? (
                      <span className="mt-1 inline-block text-[10px] uppercase tracking-wide text-accent">
                        Cross-schema
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="font-mono text-sm font-semibold text-text">
                      {item.confidence_score.toFixed(0)}
                    </span>{" "}
                    <ConfidenceLabel label={item.confidence_label} />
                  </td>
                  <td className="max-w-44 px-3 py-2.5 text-text">{item.cardinality}</td>
                  <td className="px-3 py-2.5">
                    <ValidationLabel status={item.validation_status} />
                  </td>
                  <td className="px-3 py-2.5 font-mono text-text-muted">
                    {item.match_ratio == null
                      ? "Not sampled"
                      : `${(item.match_ratio * 100).toFixed(2)}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {relationships.length > PAGE_SIZE ? (
        <div className="flex items-center justify-end gap-2 border-t border-border px-3 py-2">
          <span className="font-mono text-[11px] text-text-muted">
            Page {safePage + 1} of {pageCount}
          </span>
          <Button
            aria-label="Previous page"
            disabled={safePage === 0}
            onClick={() => onPageChange(safePage - 1)}
            size="icon"
            type="button"
            variant="ghost"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
          </Button>
          <Button
            aria-label="Next page"
            disabled={safePage >= pageCount - 1}
            onClick={() => onPageChange(safePage + 1)}
            size="icon"
            type="button"
            variant="ghost"
          >
            <ChevronRight aria-hidden="true" className="size-4" />
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function SortableHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: "asc" | "desc";
  onClick: () => void;
}) {
  const Icon = !active ? ArrowUpDown : direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
      className="border-b border-border p-0"
    >
      <button
        className="flex w-full items-center gap-1.5 px-3 py-2 font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
        onClick={onClick}
        type="button"
      >
        {label}
        <Icon aria-hidden="true" className="size-3" />
      </button>
    </th>
  );
}

function Endpoint({ endpoint }: { endpoint: RelationshipListItem["source"] }) {
  return (
    <div>
      <div className="font-mono text-[11px] text-text-muted">
        {endpoint.schema_name}.{endpoint.table_name}
      </div>
      <div className="mt-0.5 font-mono text-xs font-medium text-text">
        {endpoint.column_name}
        <span className="ml-1.5 text-[10px] font-normal text-text-muted">{endpoint.datatype}</span>
      </div>
    </div>
  );
}

export function ConfidenceLabel({ label }: { label: string }) {
  const tone =
    label === "HIGH"
      ? "text-success"
      : label === "MEDIUM-HIGH" || label === "MEDIUM"
        ? "text-warning"
        : "text-text-muted";
  return <span className={`text-[10px] font-semibold ${tone}`}>{label}</span>;
}

export function ValidationLabel({ status }: { status: string }) {
  const tone =
    status === "VALIDATED"
      ? "border-success/40 text-success"
      : status === "FAILED"
        ? "border-danger/40 text-danger"
        : status === "SKIPPED"
          ? "border-warning/40 text-warning"
          : "border-border text-text-muted";
  const title = {
    VALIDATED: "Bounded sampling completed.",
    NOT_RUN: "Sampling was not requested; this is not a failure.",
    SKIPPED: "Validation was intentionally skipped.",
    FAILED: "The bounded validation operation failed.",
  }[status];
  return (
    <span
      className={`inline-flex border px-1.5 py-0.5 font-mono text-[10px] ${tone}`}
      title={title}
    >
      {status}
    </span>
  );
}
