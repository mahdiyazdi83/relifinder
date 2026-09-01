"""Reusable ReliFinder analysis pipeline with bounded progress and cancellation hooks."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event
from typing import Any

from oracle_relationship_discovery.analysis.candidate_generator import generate_candidates
from oracle_relationship_discovery.analysis.relationship_validator import validate_candidates
from oracle_relationship_discovery.config import AppConfig
from oracle_relationship_discovery.db.connection import connection_pool
from oracle_relationship_discovery.db.data_sampler import OracleDataSampler
from oracle_relationship_discovery.db.metadata_repository import MetadataRepository
from oracle_relationship_discovery.models import AnalysisStats, ValidationStatus
from oracle_relationship_discovery.output.analysis_results import write_analysis_results
from oracle_relationship_discovery.output.csv_report import write_csv
from oracle_relationship_discovery.output.erd_builder import build_erd_model
from oracle_relationship_discovery.output.erd_models import ErdExportOptions
from oracle_relationship_discovery.output.erd_service import export_erd
from oracle_relationship_discovery.output.html_report import write_html
from oracle_relationship_discovery.output.schema_metadata import write_schema_metadata

LOGGER = logging.getLogger(__name__)


class AnalysisPhase(str, Enum):
    READING_METADATA = "READING_METADATA"
    BUILDING_CANDIDATES = "BUILDING_CANDIDATES"
    VALIDATING_CANDIDATES = "VALIDATING_CANDIDATES"
    SCORING = "SCORING"
    WRITING_ARTIFACTS = "WRITING_ARTIFACTS"


@dataclass(frozen=True, slots=True)
class AnalysisProgress:
    phase: AnalysisPhase
    message: str
    current: int | None = None
    total: int | None = None
    stats: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    stats: AnalysisStats
    relationships_in_report: int
    mode: str
    elapsed_seconds: float
    run_directory: Path


class AnalysisCancelled(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise AnalysisCancelled("Analysis cancellation was requested.")


ProgressCallback = Callable[[AnalysisProgress], None]
ConnectionFactory = Callable[[], Any]


def run_analysis(
    config: AppConfig,
    run_directory: Path,
    *,
    acquire_connection: ConnectionFactory | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
    generated_at: str,
) -> AnalysisResult:
    """Execute the same real pipeline for CLI and GUI callers."""
    token = cancellation_token or CancellationToken()
    started = time.monotonic()
    run_directory.mkdir(parents=True, exist_ok=True)

    if acquire_connection is None:
        with connection_pool(
            config.database,
            config.performance.query_timeout_seconds,
            config.performance.max_workers,
        ) as pooled_acquire:
            return run_analysis(
                config,
                run_directory,
                acquire_connection=pooled_acquire,
                progress_callback=progress_callback,
                cancellation_token=token,
                generated_at=generated_at,
            )

    def emit(
        phase: AnalysisPhase,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
        stats: dict[str, int] | None = None,
    ) -> None:
        if progress_callback:
            progress_callback(AnalysisProgress(phase, message, current, total, stats))

    token.raise_if_cancelled()
    emit(AnalysisPhase.READING_METADATA, "Reading Oracle metadata")
    with acquire_connection() as connection:
        tables = MetadataRepository(connection).load(config.schemas)
    columns = sum(len(table.columns) for table in tables)
    metadata_stats = {
        "schemas": len({table.schema for table in tables}),
        "tables": len(tables),
        "columns": columns,
    }
    emit(AnalysisPhase.READING_METADATA, "Oracle metadata loaded", stats=metadata_stats)

    token.raise_if_cancelled()
    emit(
        AnalysisPhase.BUILDING_CANDIDATES,
        "Building relationship candidates",
        stats=metadata_stats,
    )
    candidates = generate_candidates(
        tables,
        config.analysis.metadata_candidate_threshold,
        config.analysis.weights,
        config.analysis.generic_entities,
    )
    candidate_stats = {**metadata_stats, "candidates_generated": len(candidates)}
    emit(
        AnalysisPhase.BUILDING_CANDIDATES,
        "Candidate discovery completed",
        stats=candidate_stats,
    )

    token.raise_if_cancelled()
    validation_total = (
        min(len(candidates), config.performance.candidate_validation_limit)
        if config.sampling.enabled
        else 0
    )
    emit(
        AnalysisPhase.VALIDATING_CANDIDATES,
        "Validating relationship candidates"
        if config.sampling.enabled
        else "Sampling disabled; using metadata evidence",
        current=0,
        total=validation_total,
        stats=candidate_stats,
    )
    interval = max(1, validation_total // 100) if validation_total else 1

    def on_validation_progress(current: int, total: int) -> None:
        if current == total or current % interval == 0:
            emit(
                AnalysisPhase.VALIDATING_CANDIDATES,
                "Validating relationship candidates",
                current=current,
                total=total,
                stats=candidate_stats,
            )

    sampler_factory = lambda: OracleDataSampler(acquire_connection, config.sampling)
    candidates, skipped_by_limit = validate_candidates(
        candidates,
        sampler_factory,
        config,
        cancellation=token,
        progress_callback=on_validation_progress,
    )

    token.raise_if_cancelled()
    emit(AnalysisPhase.SCORING, "Finalizing scores", stats=candidate_stats)
    report_candidates = [
        candidate
        for candidate in candidates
        if candidate.score >= config.analysis.min_report_confidence
    ]
    validated = sum(
        candidate.evidence.status == ValidationStatus.VALIDATED for candidate in candidates
    )
    stats = AnalysisStats(
        schemas=metadata_stats["schemas"],
        tables=len(tables),
        columns=columns,
        candidates_generated=len(candidates),
        candidates_validated=validated,
        candidates_skipped_by_limit=skipped_by_limit,
    )
    final_stats = {
        **candidate_stats,
        "candidates_validated": validated,
        "candidates_skipped": skipped_by_limit,
        "relationships_in_report": len(report_candidates),
    }

    token.raise_if_cancelled()
    emit(AnalysisPhase.WRITING_ARTIFACTS, "Writing completed-run artifacts", stats=final_stats)
    mode = "sampled" if config.sampling.enabled else "metadata-only"
    erd_model = build_erd_model(tables, candidates)
    write_schema_metadata(run_directory / "schema-metadata.json", tables, generated_at)
    write_analysis_results(
        run_directory / "analysis-results.json",
        erd_model.relationships,
        mode,
        generated_at,
    )
    erd_results = []
    if config.erd.enabled:
        erd_results = export_erd(
            erd_model,
            run_directory / "erd",
            ErdExportOptions(
                format=config.erd.format,
                scope=config.erd.scope,
                min_confidence=config.erd.min_confidence,
                schemas=config.erd.schemas,
                max_relationships=config.erd.max_relationships,
                exclude_generic=config.erd.exclude_generic,
                generic_entities=config.analysis.generic_entities,
                include_isolated_tables=config.erd.include_isolated_tables,
                validation_statuses=config.erd.validation_statuses,
            ),
        )
    write_csv(run_directory / "relationships.csv", report_candidates, mode, generated_at)
    write_html(
        run_directory / "relationship-report.html",
        report_candidates,
        stats,
        analysis_mode=mode,
        generated_at=generated_at,
        erd_exports=erd_results,
    )
    return AnalysisResult(
        stats=stats,
        relationships_in_report=len(report_candidates),
        mode=mode,
        elapsed_seconds=round(time.monotonic() - started, 3),
        run_directory=run_directory,
    )
