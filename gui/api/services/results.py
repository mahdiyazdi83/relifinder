from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass

from pydantic import ValidationError

from gui.api.errors import ApiProblem
from gui.api.schemas.relationships import (
    RelationshipDetail,
    RelationshipEndpoint,
    RelationshipListItem,
    RelationshipListResponse,
    RelationshipScoreBreakdown,
    RelationshipValidationEvidence,
)
from gui.api.services.runs import CompletedRun, RunService
from oracle_relationship_discovery.output.analysis_results import (
    AnalysisResultsError,
    read_analysis_results,
)
from oracle_relationship_discovery.output.erd_models import ErdRelationship


@dataclass(frozen=True, slots=True)
class _CachedResults:
    completed: CompletedRun
    items: tuple[RelationshipListItem, ...]
    details: dict[str, RelationshipDetail]


class RelationshipResultsService:
    def __init__(self, runs: RunService, *, max_cached_runs: int = 8) -> None:
        if max_cached_runs <= 0:
            raise ValueError("Result cache size must be greater than zero")
        self.runs = runs
        self.max_cached_runs = max_cached_runs
        self._cache: OrderedDict[str, _CachedResults] = OrderedDict()
        self._lock = threading.RLock()

    def list(self, run_id: str) -> RelationshipListResponse:
        cached = self._load(run_id)
        return RelationshipListResponse(
            run_id=run_id,
            summary=cached.completed.summary,
            total=len(cached.items),
            relationships=cached.items,
        )

    def detail(self, run_id: str, relationship_id: str) -> RelationshipDetail:
        cached = self._load(run_id)
        detail = cached.details.get(relationship_id)
        if detail is None:
            raise ApiProblem(
                404,
                "RELATIONSHIP_NOT_FOUND",
                "The relationship was not found in this completed run.",
            )
        return detail

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _load(self, run_id: str) -> _CachedResults:
        completed = self.runs.completed(run_id)
        with self._lock:
            cached = self._cache.get(run_id)
            if cached is not None:
                self._cache.move_to_end(run_id)
                return cached

        artifact = completed.run_directory / "analysis-results.json"
        if not artifact.is_file():
            raise ApiProblem(
                409,
                "RESULTS_ARTIFACT_UNAVAILABLE",
                "The completed analysis results artifact is unavailable.",
            )
        try:
            relationships = read_analysis_results(artifact)
            selected = tuple(
                item
                for item in relationships
                if item.confidence_score >= completed.min_report_confidence
            )
            details = {_relationship_id(item): _detail(item) for item in selected}
            if len(details) != len(selected):
                raise ValueError("Duplicate or colliding relationship identity")
            items = tuple(
                sorted(
                    (_list_item(item) for item in selected),
                    key=lambda item: (
                        -item.confidence_score,
                        item.source.schema_name,
                        item.source.table_name,
                        item.source.column_name,
                        item.target.schema_name,
                        item.target.table_name,
                        item.target.column_name,
                    ),
                )
            )
        except OSError:
            raise ApiProblem(
                409,
                "RESULTS_ARTIFACT_UNAVAILABLE",
                "The completed analysis results artifact is unavailable.",
            ) from None
        except (AnalysisResultsError, ValidationError, ValueError):
            raise ApiProblem(
                422,
                "RESULTS_ARTIFACT_CORRUPT",
                "The completed analysis results artifact could not be read safely.",
            ) from None

        cached = _CachedResults(completed, items, details)
        with self._lock:
            self._cache[run_id] = cached
            self._cache.move_to_end(run_id)
            while len(self._cache) > self.max_cached_runs:
                self._cache.popitem(last=False)
        return cached


def _relationship_id(item: ErdRelationship) -> str:
    directional_key = "\0".join(item.key).encode("utf-8")
    return hashlib.sha256(directional_key).hexdigest()


def _endpoint(
    schema: str,
    table: str,
    column: str,
    datatype: str,
) -> RelationshipEndpoint:
    return RelationshipEndpoint(
        schema_name=schema,
        table_name=table,
        column_name=column,
        datatype=datatype,
    )


def _list_item(item: ErdRelationship) -> RelationshipListItem:
    return RelationshipListItem(
        id=_relationship_id(item),
        source=_endpoint(
            item.source_schema,
            item.source_table,
            item.source_column,
            item.source_datatype,
        ),
        target=_endpoint(
            item.target_schema,
            item.target_table,
            item.target_column,
            item.target_datatype,
        ),
        confidence_score=item.confidence_score,
        confidence_label=item.confidence_label,
        cardinality=item.cardinality,
        validation_status=item.validation_status,
        match_ratio=item.match_ratio,
        cross_schema=item.cross_schema,
        target_key_type=item.target_key_type,
    )


def _detail(item: ErdRelationship) -> RelationshipDetail:
    base = _list_item(item)
    return RelationshipDetail(
        **base.model_dump(),
        score_breakdown=RelationshipScoreBreakdown(
            name=item.name_score,
            datatype=item.datatype_score,
            target_key=item.key_score,
            overlap=item.data_overlap_score,
            consistency=item.consistency_score,
            structure=item.structure_score,
        ),
        validation=RelationshipValidationEvidence(
            status=item.validation_status,
            sample_size=item.sample_size,
            matched_values=item.matched_values,
            unmatched_values=item.unmatched_values,
            match_ratio=item.match_ratio,
            source_uniqueness_ratio=item.source_uniqueness_ratio,
            target_uniqueness_ratio=item.target_uniqueness_ratio,
            target_sample_size=item.target_sample_size,
            source_null_ratio=item.source_null_ratio,
            sampling_used=item.sampling_used,
        ),
        cardinality_confidence=item.cardinality_confidence,
        cardinality_explanation=item.cardinality_explanation,
        explanation=item.explanation,
    )
