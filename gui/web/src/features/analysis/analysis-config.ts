import { z } from "zod";

import type { AnalysisConfiguration, AnalysisProfile } from "../../api/client";

export const profilePresets: Record<
  Exclude<AnalysisProfile, "CUSTOM">,
  Pick<
    AnalysisConfiguration,
    | "metadata_candidate_threshold"
    | "max_source_rows"
    | "max_target_rows"
    | "bind_batch_size"
    | "sampling_mode"
    | "max_workers"
    | "candidate_validation_limit"
    | "query_timeout_seconds"
  >
> = {
  FAST: {
    metadata_candidate_threshold: 55,
    max_source_rows: 1000,
    max_target_rows: 2000,
    bind_batch_size: 250,
    sampling_mode: "first",
    max_workers: 1,
    candidate_validation_limit: 300,
    query_timeout_seconds: 10,
  },
  BALANCED: {
    metadata_candidate_threshold: 40,
    max_source_rows: 3000,
    max_target_rows: 5000,
    bind_batch_size: 500,
    sampling_mode: "first",
    max_workers: 2,
    candidate_validation_limit: 1000,
    query_timeout_seconds: 15,
  },
  THOROUGH: {
    metadata_candidate_threshold: 30,
    max_source_rows: 5000,
    max_target_rows: 10000,
    bind_batch_size: 500,
    sampling_mode: "sample",
    max_workers: 4,
    candidate_validation_limit: 3000,
    query_timeout_seconds: 30,
  },
};

export const defaultConfiguration: AnalysisConfiguration = {
  profile: "BALANCED",
  ...profilePresets.BALANCED,
  min_report_confidence: 40,
  sampling_enabled: true,
  erd_min_confidence: 80,
  erd_scope: "full",
  erd_exclude_generic: false,
};

export const analysisConfigurationSchema = z.object({
  profile: z.enum(["FAST", "BALANCED", "THOROUGH", "CUSTOM"]),
  metadata_candidate_threshold: z.number().min(0).max(100),
  min_report_confidence: z.number().min(0).max(100),
  sampling_enabled: z.boolean(),
  max_source_rows: z.number().int().min(1).max(100000),
  max_target_rows: z.number().int().min(1).max(100000),
  bind_batch_size: z.number().int().min(1).max(1000),
  sampling_mode: z.enum(["first", "sample"]),
  max_workers: z.number().int().min(1).max(8),
  candidate_validation_limit: z.number().int().min(1).max(100000),
  query_timeout_seconds: z.number().int().min(1).max(300),
  erd_min_confidence: z.number().min(0).max(100),
  erd_scope: z.enum(["full", "schema", "cross-schema"]),
  erd_exclude_generic: z.boolean(),
});
