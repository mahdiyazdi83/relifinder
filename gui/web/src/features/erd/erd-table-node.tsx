import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { useErdNodeActions } from "./erd-node-actions";
import { columnHandle } from "./erd-adapter";
import type { ErdTableNode } from "./erd-types";

export function ErdTableNodeView({ id, data, selected }: NodeProps<ErdTableNode>) {
  const { toggleExpanded } = useErdNodeActions();
  const table = data.table;
  return (
    <article
      className={`overflow-hidden border bg-surface font-mono shadow-[0_8px_24px_rgba(0,0,0,0.18)] transition-[border-color,box-shadow] ${
        selected
          ? "border-accent shadow-[0_0_0_2px_color-mix(in_srgb,var(--rf-accent)_24%,transparent)]"
          : data.neighborHighlighted
            ? "border-text-muted"
            : "border-border"
      }`}
      style={{ width: data.width }}
    >
      <header className="border-b border-border bg-surface-elevated px-3 py-2">
        <p className="truncate text-[10px] uppercase tracking-widest text-text-muted">
          {table.schema_name}
        </p>
        <h2 className="truncate text-sm font-semibold text-text">{table.table_name}</h2>
      </header>
      <div>
        {data.visibleColumns.map((column) => (
          <div
            className="relative grid h-6 grid-cols-[2.8rem_minmax(0,1fr)_5.5rem] items-center border-b border-border/60 px-2 text-[10px] last:border-b-0"
            key={column.name}
          >
            {column.targetConnected ? (
              <Handle
                aria-label={`Incoming relationship handle for ${column.name}`}
                className="!size-2 !border-background !bg-accent"
                id={columnHandle("target", column.name)}
                isConnectable={false}
                position={Position.Left}
                type="target"
              />
            ) : null}
            <span className="text-[9px] font-semibold text-accent">
              {column.primary_key
                ? "PK"
                : column.unique_key
                  ? "UK"
                  : column.composite_key
                    ? "CK"
                    : ""}
            </span>
            <span className="truncate text-text" title={column.name}>
              {column.name}
            </span>
            <span
              className="truncate text-right text-[9px] text-text-muted"
              title={column.datatype}
            >
              {column.datatype}
            </span>
            {column.sourceConnected ? (
              <Handle
                aria-label={`Outgoing relationship handle for ${column.name}`}
                className="!size-2 !border-background !bg-accent"
                id={columnHandle("source", column.name)}
                isConnectable={false}
                position={Position.Right}
                type="source"
              />
            ) : null}
          </div>
        ))}
      </div>
      {data.hiddenColumnCount > 0 ? (
        <button
          aria-label={`Expand ${table.schema_name}.${table.table_name}`}
          className="nodrag flex h-7 w-full items-center justify-center gap-1 border-t border-border bg-surface-elevated text-[10px] text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
          onClick={(event) => {
            event.stopPropagation();
            toggleExpanded(id);
          }}
          type="button"
        >
          <ChevronDown aria-hidden="true" className="size-3" />+ {data.hiddenColumnCount} more
        </button>
      ) : table.columns.length > 8 ? (
        <button
          aria-label={`Collapse ${table.schema_name}.${table.table_name}`}
          className="nodrag flex h-7 w-full items-center justify-center gap-1 border-t border-border bg-surface-elevated text-[10px] text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
          onClick={(event) => {
            event.stopPropagation();
            toggleExpanded(id);
          }}
          type="button"
        >
          <ChevronUp aria-hidden="true" className="size-3" /> Collapse
        </button>
      ) : null}
    </article>
  );
}
