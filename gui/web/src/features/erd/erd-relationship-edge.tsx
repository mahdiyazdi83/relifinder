import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

import type { ErdRelationshipEdge } from "./erd-types";

export function ErdRelationshipEdgeView({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
  selected,
}: EdgeProps<ErdRelationshipEdge>) {
  const relationship = data!.relationship;
  const active = Boolean(selected || data!.highlighted);
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 4,
    offset: 20,
  });
  const unknown = relationship.cardinality === "Unknown / Insufficient Evidence";
  const width =
    relationship.confidence_score >= 85 ? 2.4 : relationship.confidence_score >= 65 ? 1.7 : 1.1;
  const dash = validationDash(relationship.validation_status, unknown);
  const opacity =
    relationship.confidence_score >= 85 ? 0.9 : relationship.confidence_score >= 65 ? 0.72 : 0.5;

  return (
    <>
      <BaseEdge
        id={id}
        markerEnd={markerEnd}
        path={path}
        style={{
          stroke: active ? "var(--rf-accent)" : "var(--rf-text-muted)",
          strokeDasharray: dash,
          strokeWidth: active ? width + 2 : width,
          opacity: active ? 1 : opacity,
        }}
      />
      <path
        className="react-flow__edge-interaction"
        d={path}
        data-testid={`erd-edge-${id}`}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
      />
      {selected ? (
        <EdgeLabelRenderer>
          <div
            className="nopan nodrag pointer-events-none absolute border border-accent bg-surface px-1.5 py-0.5 font-mono text-[9px] text-text shadow-sm"
            data-relationship-edge-label={id}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` }}
          >
            {relationship.confidence_score.toFixed(0)} · {cardinalityMark(relationship.cardinality)}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

function validationDash(status: string, unknown: boolean): string | undefined {
  if (status === "FAILED") return "1 5";
  if (status === "SKIPPED") return "3 5";
  if (status === "NOT_RUN") return unknown ? "8 4 2 4" : "7 4";
  return unknown ? "8 4" : undefined;
}

function cardinalityMark(cardinality: string): string {
  if (cardinality === "Many-to-One") return "* → 1";
  if (cardinality === "One-to-Many") return "1 → *";
  if (cardinality === "One-to-One") return "1 → 1";
  return "?";
}
