import { ChevronDown, Gauge, SlidersHorizontal } from "lucide-react";
import { type FormEvent, useState } from "react";

import type { AnalysisConfiguration, AnalysisProfile } from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  analysisConfigurationSchema,
  defaultConfiguration,
  profilePresets,
} from "./analysis-config";

const profiles: {
  key: Exclude<AnalysisProfile, "CUSTOM">;
  label: string;
  description: string;
}[] = [
  { key: "FAST", label: "Fast", description: "Lower database load, less validation depth" },
  { key: "BALANCED", label: "Balanced", description: "Recommended default" },
  {
    key: "THOROUGH",
    label: "Thorough",
    description: "More validation, higher database workload",
  },
];

type AdvancedNumberKey =
  | "metadata_candidate_threshold"
  | "max_source_rows"
  | "max_target_rows"
  | "bind_batch_size"
  | "max_workers"
  | "candidate_validation_limit"
  | "query_timeout_seconds";

interface AnalysisConfigurationFormProps {
  selectedSchemas: string[];
  submitting: boolean;
  errorMessage: string | null;
  onSubmit: (configuration: AnalysisConfiguration) => void;
}

export function AnalysisConfigurationForm({
  selectedSchemas,
  submitting,
  errorMessage,
  onSubmit,
}: AnalysisConfigurationFormProps) {
  const [configuration, setConfiguration] = useState<AnalysisConfiguration>(defaultConfiguration);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  function selectProfile(profile: Exclude<AnalysisProfile, "CUSTOM">) {
    setConfiguration((current) => ({
      ...current,
      ...profilePresets[profile],
      profile,
    }));
    setValidationMessage(null);
  }

  function updateAdvanced(key: AdvancedNumberKey, value: number) {
    setConfiguration((current) => ({ ...current, [key]: value, profile: "CUSTOM" }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const result = analysisConfigurationSchema.safeParse(configuration);
    if (!result.success) {
      setValidationMessage("Values must stay within the documented ranges.");
      return;
    }
    setValidationMessage(null);
    onSubmit(result.data);
  }

  return (
    <form className="space-y-6" noValidate onSubmit={submit}>
      <fieldset disabled={submitting}>
        <legend className="flex items-center gap-2 text-sm font-semibold text-text">
          <Gauge aria-hidden="true" className="size-4 text-accent" />
          Analysis profile
        </legend>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {profiles.map((profile) => {
            const selected = configuration.profile === profile.key;
            return (
              <button
                aria-pressed={selected}
                className={`border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                  selected
                    ? "border-accent bg-accent/8"
                    : "border-border bg-surface hover:bg-surface-elevated"
                }`}
                key={profile.key}
                onClick={() => selectProfile(profile.key)}
                type="button"
              >
                <span className="block text-sm font-medium text-text">{profile.label}</span>
                <span className="mt-1 block text-xs leading-5 text-text-muted">
                  {profile.description}
                </span>
              </button>
            );
          })}
        </div>
        {configuration.profile === "CUSTOM" ? (
          <p className="mt-2 font-mono text-[11px] text-warning">
            Custom · choosing a profile again resets its advanced values.
          </p>
        ) : null}
      </fieldset>

      <div>
        <h2 className="text-sm font-semibold text-text">Selected schemas</h2>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selectedSchemas.map((schema) => (
            <span
              className="border border-border bg-surface-elevated px-2 py-1 font-mono text-xs text-text"
              key={schema}
            >
              {schema}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-4 border-y border-border py-5 sm:grid-cols-3">
        <label className="flex items-center gap-2 text-sm text-text">
          <input
            checked={configuration.sampling_enabled}
            className="size-4 accent-[var(--rf-accent)]"
            onChange={(event) =>
              setConfiguration((current) => ({
                ...current,
                sampling_enabled: event.target.checked,
              }))
            }
            type="checkbox"
          />
          Sampling enabled
        </label>
        <NumberField
          label="Minimum report confidence"
          max={100}
          min={0}
          onChange={(value) =>
            setConfiguration((current) => ({ ...current, min_report_confidence: value }))
          }
          value={configuration.min_report_confidence}
        />
        <NumberField
          label="Minimum ERD confidence"
          max={100}
          min={0}
          onChange={(value) =>
            setConfiguration((current) => ({ ...current, erd_min_confidence: value }))
          }
          value={configuration.erd_min_confidence}
        />
      </div>

      <details className="border border-border bg-surface">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          <SlidersHorizontal aria-hidden="true" className="size-4 text-accent" />
          Advanced settings
          <ChevronDown aria-hidden="true" className="ml-auto size-4 text-text-muted" />
        </summary>
        <div className="grid gap-4 border-t border-border p-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField
            label="Metadata candidate threshold"
            max={100}
            min={0}
            onChange={(value) => updateAdvanced("metadata_candidate_threshold", value)}
            value={configuration.metadata_candidate_threshold}
          />
          <NumberField
            label="Maximum source rows"
            max={100000}
            min={1}
            onChange={(value) => updateAdvanced("max_source_rows", value)}
            value={configuration.max_source_rows}
          />
          <NumberField
            label="Maximum target rows"
            max={100000}
            min={1}
            onChange={(value) => updateAdvanced("max_target_rows", value)}
            value={configuration.max_target_rows}
          />
          <NumberField
            label="Bind batch size"
            max={1000}
            min={1}
            onChange={(value) => updateAdvanced("bind_batch_size", value)}
            value={configuration.bind_batch_size}
          />
          <NumberField
            label="Worker count"
            max={8}
            min={1}
            onChange={(value) => updateAdvanced("max_workers", value)}
            value={configuration.max_workers}
          />
          <NumberField
            label="Candidate validation limit"
            max={100000}
            min={1}
            onChange={(value) => updateAdvanced("candidate_validation_limit", value)}
            value={configuration.candidate_validation_limit}
          />
          <NumberField
            label="Query timeout seconds"
            max={300}
            min={1}
            onChange={(value) => updateAdvanced("query_timeout_seconds", value)}
            value={configuration.query_timeout_seconds}
          />
          <label className="text-xs font-medium text-text-muted">
            Sampling mode
            <select
              className="mt-1.5 h-9 w-full border border-border bg-background px-2 text-sm text-text"
              onChange={(event) =>
                setConfiguration((current) => ({
                  ...current,
                  sampling_mode: event.target.value as "first" | "sample",
                  profile: "CUSTOM",
                }))
              }
              value={configuration.sampling_mode}
            >
              <option value="first">First rows</option>
              <option value="sample">Oracle block sample</option>
            </select>
          </label>
          <label className="text-xs font-medium text-text-muted">
            ERD scope
            <select
              className="mt-1.5 h-9 w-full border border-border bg-background px-2 text-sm text-text"
              onChange={(event) =>
                setConfiguration((current) => ({
                  ...current,
                  erd_scope: event.target.value as AnalysisConfiguration["erd_scope"],
                  profile: "CUSTOM",
                }))
              }
              value={configuration.erd_scope}
            >
              <option value="full">Full</option>
              <option value="schema">Per schema</option>
              <option value="cross-schema">Cross-schema</option>
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm text-text">
            <input
              checked={configuration.erd_exclude_generic}
              className="size-4 accent-[var(--rf-accent)]"
              onChange={(event) =>
                setConfiguration((current) => ({
                  ...current,
                  erd_exclude_generic: event.target.checked,
                  profile: "CUSTOM",
                }))
              }
              type="checkbox"
            />
            Exclude generic ERD entities
          </label>
        </div>
      </details>

      {validationMessage || errorMessage ? (
        <div
          className="border-l-2 border-danger bg-danger/8 px-4 py-3 text-sm text-danger"
          role="alert"
        >
          {validationMessage ?? errorMessage}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-4 border-t border-border pt-4">
        <p className="max-w-xl text-xs leading-5 text-text-muted">
          Runs execute locally. Cancellation takes effect at safe boundaries or after the current
          bounded Oracle call returns.
        </p>
        <Button disabled={submitting} type="submit">
          {submitting ? "Starting…" : "Run Analysis"}
        </Button>
      </div>
    </form>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="text-xs font-medium text-text-muted">
      {label}
      <input
        className="mt-1.5 h-9 w-full border border-border bg-background px-2 font-mono text-sm text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        max={max}
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        type="number"
        value={value}
      />
    </label>
  );
}
