import { ArrowRight, X } from "lucide-react";

import type { RelationshipDetail } from "../../api/client";
import { Button } from "../../components/ui/button";
import { toDisplayMessage } from "../../api/errors";
import { ConfidenceLabel, ValidationLabel } from "./relationship-table";

export function RelationshipInspector({
  detail,
  loading,
  error,
  onClose,
}: {
  detail: RelationshipDetail | undefined;
  loading: boolean;
  error: unknown;
  onClose: () => void;
}) {
  return (
    <aside
      aria-label="Relationship inspector"
      className="min-h-[28rem] border-l border-border bg-surface max-lg:border-l-0 max-lg:border-t"
    >
      <div className="flex h-10 items-center border-b border-border bg-surface-elevated px-3">
        <h2 className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
          Inspector
        </h2>
        <Button
          aria-label="Close inspector"
          className="ml-auto"
          onClick={onClose}
          size="icon"
          type="button"
          variant="ghost"
        >
          <X aria-hidden="true" className="size-4" />
        </Button>
      </div>
      {loading ? (
        <p className="p-4 text-sm text-text-muted" role="status">
          Loading relationship evidence…
        </p>
      ) : error ? (
        <p
          className="m-4 border-l-2 border-danger bg-danger/8 px-3 py-2 text-sm text-danger"
          role="alert"
        >
          {toDisplayMessage(error)}
        </p>
      ) : detail ? (
        <div className="p-4">
          <div className="font-mono">
            <p className="text-[11px] text-text-muted">
              {detail.source.schema_name}.{detail.source.table_name}
            </p>
            <p className="text-sm font-semibold text-text">{detail.source.column_name}</p>
            <ArrowRight aria-hidden="true" className="my-2 size-4 text-accent" />
            <p className="text-[11px] text-text-muted">
              {detail.target.schema_name}.{detail.target.table_name}
            </p>
            <p className="text-sm font-semibold text-text">{detail.target.column_name}</p>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 border-y border-border py-3">
            <strong className="font-mono text-xl text-text">
              {detail.confidence_score.toFixed(0)}
            </strong>
            <ConfidenceLabel label={detail.confidence_label} />
            <ValidationLabel status={detail.validation_status} />
            <span className="text-xs text-text-muted">{detail.cardinality}</span>
          </div>

          <InspectorSection title="Score evidence">
            <dl className="divide-y divide-border/70">
              {Object.entries(detail.score_breakdown).map(([label, value]) => (
                <MetricRow key={label} label={scoreLabel(label)} value={formatNumber(value)} />
              ))}
            </dl>
          </InspectorSection>

          <InspectorSection title="Sampling">
            {detail.validation.sampling_used ? (
              <dl className="divide-y divide-border/70">
                <MetricRow label="Status" value={detail.validation.status} />
                <MetricRow
                  label="Sample size"
                  value={detail.validation.sample_size.toLocaleString()}
                />
                <MetricRow
                  label="Matched"
                  value={detail.validation.matched_values.toLocaleString()}
                />
                <MetricRow
                  label="Unmatched"
                  value={detail.validation.unmatched_values.toLocaleString()}
                />
                <MetricRow label="Match ratio" value={formatRatio(detail.validation.match_ratio)} />
                <MetricRow
                  label="Source uniqueness"
                  value={formatRatio(detail.validation.source_uniqueness_ratio)}
                />
                <MetricRow
                  label="Target uniqueness"
                  value={formatRatio(detail.validation.target_uniqueness_ratio)}
                />
                <MetricRow
                  label="Source null ratio"
                  value={formatRatio(detail.validation.source_null_ratio)}
                />
              </dl>
            ) : (
              <p className="text-sm text-text-muted">Not sampled</p>
            )}
          </InspectorSection>

          <InspectorSection title="Cardinality">
            <p className="text-sm font-medium text-text">{detail.cardinality}</p>
            <p className="mt-1 text-xs text-text-muted">
              Confidence {(detail.cardinality_confidence * 100).toFixed(0)}%
            </p>
            <p className="mt-2 text-xs leading-5 text-text-muted">
              {detail.cardinality_explanation}
            </p>
            {detail.cardinality === "Unknown / Insufficient Evidence" ? (
              <p className="mt-2 border-l border-warning pl-3 text-xs leading-5 text-text-muted">
                Relationship confidence and cardinality confidence measure different evidence.
              </p>
            ) : null}
          </InspectorSection>

          <InspectorSection title="Explanation">
            <p className="text-sm leading-6 text-text-muted">{detail.explanation}</p>
          </InspectorSection>
        </div>
      ) : (
        <div className="grid min-h-72 place-items-center p-5 text-center">
          <div>
            <p className="text-sm font-medium text-text">Select a relationship</p>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              Full score, sampling, cardinality, and core explanation will appear here.
            </p>
          </div>
        </div>
      )}
    </aside>
  );
}

function InspectorSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-border py-4">
      <h3 className="mb-2 font-mono text-[10px] uppercase tracking-widest text-text-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-xs">
      <dt className="text-text-muted">{label}</dt>
      <dd className="font-mono text-text">{value}</dd>
    </div>
  );
}

function scoreLabel(value: string): string {
  return (
    {
      name: "Name",
      datatype: "Datatype",
      target_key: "Target key",
      overlap: "Overlap",
      consistency: "Consistency",
      structure: "Structure",
    }[value] ?? value
  );
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatRatio(value: number | null | undefined): string {
  return value == null ? "Unavailable" : `${(value * 100).toFixed(2)}%`;
}
