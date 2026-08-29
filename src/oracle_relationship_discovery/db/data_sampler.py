"""Low-impact, bounded source/target sampling with no value persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from oracle_relationship_discovery.config import SamplingConfig
from oracle_relationship_discovery.db.connection import execute_select, quote_identifier
from oracle_relationship_discovery.models import (
    RelationshipCandidate,
    ValidationEvidence,
    ValidationStatus,
)


class OracleDataSampler:
    def __init__(self, connection_factory: Callable, sampling: SamplingConfig) -> None:
        self.connection_factory = connection_factory
        self.sampling = sampling

    @staticmethod
    def _qualified(schema: str, table: str) -> str:
        return f"{quote_identifier(schema)}.{quote_identifier(table)}"

    def _sample_values(
        self, cursor: Any, schema: str, table: str, column: str, limit: int
    ) -> list[Any]:
        qualified = self._qualified(schema, table)
        quoted_column = quote_identifier(column)
        sample_clause = " SAMPLE BLOCK (1)" if self.sampling.mode == "sample" else ""
        sql = f"""
            SELECT sampled_value
            FROM (
                SELECT {quoted_column} AS sampled_value
                FROM {qualified}{sample_clause}
                WHERE {quoted_column} IS NOT NULL
                  AND ROWNUM <= :row_limit
            )
        """
        return [row[0] for row in execute_select(cursor, sql, {"row_limit": limit}).fetchall()]

    def _find_matches(
        self, cursor: Any, candidate: RelationshipCandidate, distinct_values: list[Any]
    ) -> set[Any]:
        matched: set[Any] = set()
        qualified = self._qualified(candidate.target.schema, candidate.target.table)
        column = quote_identifier(candidate.target.name)
        batch_size = self.sampling.bind_batch_size
        for offset in range(0, len(distinct_values), batch_size):
            batch = distinct_values[offset : offset + batch_size]
            binds = {f"v{index}": value for index, value in enumerate(batch)}
            placeholders = ", ".join(f":{name}" for name in binds)
            sql = f"SELECT DISTINCT {column} FROM {qualified} WHERE {column} IN ({placeholders})"
            matched.update(row[0] for row in execute_select(cursor, sql, binds).fetchall())
        return matched

    def validate(self, candidate: RelationshipCandidate) -> None:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            source_values = self._sample_values(
                cursor,
                candidate.source.schema,
                candidate.source.table,
                candidate.source.name,
                self.sampling.max_source_rows,
            )
            if not source_values:
                candidate.evidence = ValidationEvidence(
                    status=ValidationStatus.SKIPPED,
                    sampling_used=True,
                    message="No non-null source values were found in the bounded sample.",
                )
                return
            distinct_source = list(dict.fromkeys(source_values))
            matched = self._find_matches(cursor, candidate, distinct_source)
            matched_rows = sum(1 for value in source_values if value in matched)
            target_uniqueness = None
            target_sample_size = 0
            if not candidate.target.is_single_column_key:
                target_values = self._sample_values(
                    cursor,
                    candidate.target.schema,
                    candidate.target.table,
                    candidate.target.name,
                    self.sampling.max_target_rows,
                )
                if target_values:
                    target_sample_size = len(target_values)
                    target_uniqueness = len(set(target_values)) / len(target_values)
            sample_size = len(source_values)
            candidate.evidence = ValidationEvidence(
                status=ValidationStatus.VALIDATED,
                sample_size=sample_size,
                matched_values=matched_rows,
                unmatched_values=sample_size - matched_rows,
                match_ratio=matched_rows / sample_size,
                source_uniqueness_ratio=len(distinct_source) / sample_size,
                target_uniqueness_ratio=target_uniqueness,
                target_sample_size=target_sample_size,
                sampling_used=True,
                message=(
                    f"Bounded validation matched {matched_rows} of {sample_size} sampled source rows "
                    f"({matched_rows / sample_size:.2%}); sampled values were not persisted."
                ),
            )
