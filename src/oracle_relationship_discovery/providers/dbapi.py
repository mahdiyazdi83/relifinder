"""Shared DB-API safety and bounded sampling primitives for SQL providers."""

from __future__ import annotations

import queue
import re
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from oracle_relationship_discovery.config import SamplingConfig
from oracle_relationship_discovery.models import (
    RelationshipCandidate,
    ValidationEvidence,
    ValidationStatus,
)

_READ_RE = re.compile(r"^\s*(?:SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|REPLACE|"
    r"CALL|DO|COPY|LOAD|GRANT|REVOKE|LOCK|UNLOCK|SET|RESET)\b",
    re.IGNORECASE,
)


def validate_identifier(
    identifier: str,
    *,
    dialect: str,
    max_length: int = 128,
    length_in_bytes: bool = False,
) -> str:
    if (
        not identifier
        or (len(identifier.encode("utf-8")) if length_in_bytes else len(identifier)) > max_length
        or any(ord(char) < 32 or ord(char) == 127 for char in identifier)
    ):
        raise ValueError(f"Unsupported or unsafe {dialect} identifier: {identifier!r}")
    return identifier


def assert_read_only(sql: str) -> None:
    without_literals = re.sub(r"'(?:''|[^'])*'", "''", sql)
    without_literals = re.sub(r'"(?:""|[^"])*"', '""', without_literals)
    without_literals = re.sub(r"`(?:``|[^`])*`", "``", without_literals)
    without_comments = re.sub(r"/\*.*?\*/|--[^\r\n]*", " ", without_literals, flags=re.DOTALL)
    if (
        not _READ_RE.match(without_comments)
        or _FORBIDDEN_RE.search(without_comments)
        or ";" in without_comments
    ):
        raise ValueError("Only read-only SELECT statements are allowed")


def execute_read(
    cursor: Any,
    sql: str,
    binds: Mapping[str, Any] | Sequence[Any] | None = None,
) -> Any:
    assert_read_only(sql)
    cursor.execute(sql, binds or ())
    return cursor


class DbApiRuntimePool:
    """Small lazy bounded pool that never persists credentials outside process memory."""

    def __init__(self, factory: Callable[[], Any], max_connections: int, display_name: str) -> None:
        self._factory = factory
        self._maximum = max_connections
        self._display_name = display_name
        self._available: queue.LifoQueue[Any] = queue.LifoQueue(max_connections)
        self._created = 0
        self._closed = False
        self._lock = threading.RLock()

    @contextmanager
    def acquire(self, timeout_seconds: int) -> Iterator[Any]:
        connection = self._take(timeout_seconds)
        healthy = True
        try:
            yield connection
        except Exception:
            healthy = False
            raise
        finally:
            try:
                connection.rollback()
            except Exception:  # noqa: BLE001 - discard broken driver connections.
                healthy = False
            self._return(connection, healthy)

    def _take(self, timeout_seconds: int) -> Any:
        with self._lock:
            if self._closed:
                raise RuntimeError(f"{self._display_name} runtime pool is closed")
            try:
                return self._available.get_nowait()
            except queue.Empty:
                if self._created < self._maximum:
                    self._created += 1
                    create = True
                else:
                    create = False
        if create:
            try:
                return self._factory()
            except Exception:
                with self._lock:
                    self._created -= 1
                raise
        try:
            return self._available.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise TimeoutError(f"Timed out waiting for a {self._display_name} connection") from exc

    def _return(self, connection: Any, healthy: bool) -> None:
        with self._lock:
            if self._closed or not healthy:
                try:
                    connection.close()
                finally:
                    self._created -= 1
                return
            self._available.put_nowait(connection)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            while True:
                try:
                    connection = self._available.get_nowait()
                except queue.Empty:
                    break
                try:
                    connection.close()
                finally:
                    self._created -= 1


class DbApiDataSampler:
    """Bounded source sampling and batched target lookup for `%s` DB-API dialects."""

    def __init__(
        self,
        connection_factory: Callable,
        sampling: SamplingConfig,
        quote_identifier: Callable[[str], str],
        *,
        table_sample_clause: str = "",
    ) -> None:
        self.connection_factory = connection_factory
        self.sampling = sampling
        self.quote_identifier = quote_identifier
        self.table_sample_clause = table_sample_clause

    def _qualified(self, schema: str, table: str) -> str:
        return f"{self.quote_identifier(schema)}.{self.quote_identifier(table)}"

    def _sample_values(
        self, cursor: Any, schema: str, table: str, column: str, limit: int
    ) -> list[Any]:
        qualified = self._qualified(schema, table)
        quoted_column = self.quote_identifier(column)
        sample_clause = self.table_sample_clause if self.sampling.mode == "sample" else ""
        sql = (
            f"SELECT {quoted_column} FROM {qualified}{sample_clause} "
            f"WHERE {quoted_column} IS NOT NULL LIMIT %s"
        )
        return [row[0] for row in execute_read(cursor, sql, (limit,)).fetchall()]

    def _find_matches(
        self, cursor: Any, candidate: RelationshipCandidate, distinct_values: list[Any]
    ) -> set[Any]:
        matched: set[Any] = set()
        qualified = self._qualified(candidate.target.schema, candidate.target.table)
        column = self.quote_identifier(candidate.target.name)
        for offset in range(0, len(distinct_values), self.sampling.bind_batch_size):
            batch = distinct_values[offset : offset + self.sampling.bind_batch_size]
            placeholders = ", ".join("%s" for _value in batch)
            sql = f"SELECT DISTINCT {column} FROM {qualified} WHERE {column} IN ({placeholders})"
            matched.update(row[0] for row in execute_read(cursor, sql, tuple(batch)).fetchall())
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
            matched_rows = sum(value in matched for value in source_values)
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
