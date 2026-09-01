from __future__ import annotations

import logging
import secrets
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gui.api.errors import ApiProblem
from gui.api.schemas.runs import (
    AnalysisConfiguration,
    RunCancelResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunProgressEvent,
    RunState,
    RunStatusResponse,
    RunSummary,
)
from gui.api.services.connection_sessions import (
    ConnectionSessionStore,
    RuntimeConnectionSession,
    SessionNotFoundError,
)
from oracle_relationship_discovery.analysis.service import (
    AnalysisCancelled,
    AnalysisProgress,
    AnalysisResult,
    CancellationToken,
    run_analysis,
)
from oracle_relationship_discovery.config import (
    AnalysisConfig,
    AppConfig,
    DatabaseConfig,
    ErdConfig,
    OutputConfig,
    PerformanceConfig,
    SamplingConfig,
)

LOGGER = logging.getLogger(__name__)
TERMINAL_STATES = {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}
PHASE_ORDER = {
    RunState.QUEUED: 0,
    RunState.READING_METADATA: 1,
    RunState.BUILDING_CANDIDATES: 2,
    RunState.VALIDATING_CANDIDATES: 3,
    RunState.SCORING: 4,
    RunState.WRITING_ARTIFACTS: 5,
    RunState.COMPLETED: 6,
}
SAFE_STATS = {
    "schemas",
    "tables",
    "columns",
    "candidates_generated",
    "candidates_validated",
    "candidates_skipped",
    "relationships_in_report",
}


class AnalysisExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AnalysisExecutor:
    def execute(
        self,
        *,
        run_id: str,
        session: RuntimeConnectionSession,
        schemas: tuple[str, ...],
        configuration: AnalysisConfiguration,
        progress_callback: Callable[[AnalysisProgress], None],
        cancellation_token: CancellationToken,
    ) -> AnalysisResult:
        raise NotImplementedError


class CoreAnalysisExecutor(AnalysisExecutor):
    def __init__(self, output_root: Path = Path("output")) -> None:
        self.output_root = output_root

    def execute(
        self,
        *,
        run_id: str,
        session: RuntimeConnectionSession,
        schemas: tuple[str, ...],
        configuration: AnalysisConfiguration,
        progress_callback: Callable[[AnalysisProgress], None],
        cancellation_token: CancellationToken,
    ) -> AnalysisResult:
        if session.resource is None:
            raise AnalysisExecutionError(
                "RECONNECT_REQUIRED",
                "The Oracle runtime connection is unavailable. Reconnect before starting analysis.",
            )
        config = _core_config(schemas, configuration, self.output_root)
        started = datetime.now().astimezone()
        incomplete = self.output_root / ".incomplete" / run_id
        try:
            result = run_analysis(
                config,
                incomplete,
                acquire_connection=lambda: session.resource.acquire(
                    configuration.query_timeout_seconds
                ),
                progress_callback=progress_callback,
                cancellation_token=cancellation_token,
                generated_at=started.isoformat(timespec="microseconds"),
            )
            cancellation_token.raise_if_cancelled()
            final_name = (
                f"{started.strftime('%Y-%m-%d_%H-%M-%S-%f_%z')}_{result.mode}_gui_{run_id[:8]}"
            )
            final_path = self.output_root.resolve() / final_name
            final_path.parent.mkdir(parents=True, exist_ok=True)
            incomplete.replace(final_path)
            return AnalysisResult(
                stats=result.stats,
                relationships_in_report=result.relationships_in_report,
                mode=result.mode,
                elapsed_seconds=result.elapsed_seconds,
                run_directory=final_path,
            )
        except AnalysisCancelled:
            raise
        except AnalysisExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - sanitize driver and pipeline failures.
            if cancellation_token.is_cancelled:
                raise AnalysisCancelled("Analysis cancellation was requested.") from None
            raise _safe_execution_error(exc) from None


@dataclass(frozen=True, slots=True)
class CompletedRun:
    run_id: str
    summary: RunSummary
    run_directory: Path
    min_report_confidence: float
    erd_min_confidence: float
    erd_scope: str


@dataclass(slots=True)
class _RunRecord:
    run_id: str
    connection_id: str
    selected_schemas: tuple[str, ...]
    configuration: AnalysisConfiguration
    token: CancellationToken
    latest: RunProgressEvent
    events: list[RunProgressEvent] = field(default_factory=list)
    condition: threading.Condition = field(default_factory=threading.Condition)
    thread: threading.Thread | None = field(default=None, repr=False)
    completed_directory: Path | None = field(default=None, repr=False)


class RunService:
    def __init__(
        self,
        sessions: ConnectionSessionStore,
        executor: AnalysisExecutor | None = None,
        *,
        max_runs: int = 100,
    ) -> None:
        self.sessions = sessions
        self.executor = executor or CoreAnalysisExecutor()
        self.max_runs = max_runs
        self._runs: dict[str, _RunRecord] = {}
        self._active_by_connection: dict[str, str] = {}
        self._lock = threading.RLock()

    def create(self, payload: RunCreateRequest) -> RunCreateResponse:
        with self._lock:
            if payload.connection_id in self._active_by_connection:
                raise ApiProblem(
                    409,
                    "ACTIVE_RUN_EXISTS",
                    "This Oracle connection already has an active analysis run.",
                )
        try:
            session = self.sessions.acquire_for_run(payload.connection_id)
        except SessionNotFoundError:
            raise ApiProblem(
                404,
                "CONNECTION_SESSION_NOT_FOUND",
                "The local Oracle connection session is missing or has expired. Reconnect first.",
            ) from None

        available = {item.name for item in session.schemas}
        missing = sorted(set(payload.schemas) - available)
        if missing:
            self.sessions.release_from_run(payload.connection_id)
            raise ApiProblem(
                400,
                "SCHEMA_NOT_AVAILABLE",
                "One or more selected schemas are not available in this connection session.",
            )

        with self._lock:
            if payload.connection_id in self._active_by_connection:
                self.sessions.release_from_run(payload.connection_id)
                raise ApiProblem(
                    409,
                    "ACTIVE_RUN_EXISTS",
                    "This Oracle connection already has an active analysis run.",
                )
            self._trim_runs_locked()
            run_id = secrets.token_urlsafe(32)
            initial = RunProgressEvent(
                sequence=0,
                run_id=run_id,
                state=RunState.QUEUED,
                message="Analysis is queued",
            )
            record = _RunRecord(
                run_id,
                payload.connection_id,
                payload.schemas,
                payload.configuration,
                CancellationToken(),
                initial,
                [initial],
            )
            self._runs[run_id] = record
            self._active_by_connection[payload.connection_id] = run_id
            thread = threading.Thread(
                target=self._execute,
                args=(record, session),
                name=f"relifinder-run-{run_id[:8]}",
                daemon=True,
            )
            record.thread = thread
            thread.start()
        return RunCreateResponse(run_id=run_id, status=RunState.QUEUED)

    def get(self, run_id: str) -> RunStatusResponse:
        record = self._record(run_id)
        with record.condition:
            event = record.latest
            return RunStatusResponse(
                **event.model_dump(),
                connection_id=record.connection_id,
                selected_schemas=record.selected_schemas,
            )

    def completed(self, run_id: str) -> CompletedRun:
        record = self._record(run_id)
        with record.condition:
            if (
                record.latest.state != RunState.COMPLETED
                or record.latest.summary is None
                or record.completed_directory is None
            ):
                raise ApiProblem(
                    409,
                    "RUN_NOT_COMPLETED",
                    "Relationship results are available only for a completed analysis run.",
                )
            return CompletedRun(
                run_id=record.run_id,
                summary=record.latest.summary,
                run_directory=record.completed_directory,
                min_report_confidence=record.configuration.min_report_confidence,
                erd_min_confidence=record.configuration.erd_min_confidence,
                erd_scope=record.configuration.erd_scope,
            )

    def cancel(self, run_id: str) -> RunCancelResponse:
        record = self._record(run_id)
        with record.condition:
            if record.latest.state in TERMINAL_STATES:
                return RunCancelResponse(run_id=run_id, status=record.latest.state)
            record.token.cancel()
            self._publish_locked(
                record,
                RunState.CANCEL_REQUESTED,
                "Cancellation requested; waiting for the current bounded operation",
                stats=record.latest.stats,
            )
            return RunCancelResponse(run_id=run_id, status=RunState.CANCEL_REQUESTED)

    def events(self, run_id: str, after_sequence: int = -1) -> Iterator[str]:
        record = self._record(run_id)
        cursor = after_sequence
        while True:
            heartbeat = False
            with record.condition:
                available = [item for item in record.events if item.sequence > cursor]
                if not available and record.latest.state not in TERMINAL_STATES:
                    record.condition.wait(timeout=15)
                    available = [item for item in record.events if item.sequence > cursor]
                if not available:
                    if record.latest.state in TERMINAL_STATES:
                        return
                    heartbeat = True
            if heartbeat:
                yield ": keep-alive\n\n"
                continue
            for event in available:
                cursor = event.sequence
                yield (
                    f"id: {event.sequence}\nevent: progress\ndata: {event.model_dump_json()}\n\n"
                )
                if event.state in TERMINAL_STATES:
                    return

    def close(self) -> None:
        with self._lock:
            records = list(self._runs.values())
        for record in records:
            if record.latest.state not in TERMINAL_STATES:
                record.token.cancel()
        for record in records:
            if record.thread and record.thread.is_alive():
                record.thread.join(timeout=2)

    def _execute(self, record: _RunRecord, session: RuntimeConnectionSession) -> None:
        try:
            result = self.executor.execute(
                run_id=record.run_id,
                session=session,
                schemas=record.selected_schemas,
                configuration=record.configuration,
                progress_callback=lambda progress: self._progress(record, progress),
                cancellation_token=record.token,
            )
            summary = RunSummary(
                schemas_analyzed=result.stats.schemas,
                tables=result.stats.tables,
                columns=result.stats.columns,
                candidates_generated=result.stats.candidates_generated,
                candidates_validated=result.stats.candidates_validated,
                candidates_skipped=result.stats.candidates_skipped_by_limit,
                relationships_in_report=result.relationships_in_report,
                run_mode=result.mode,
                elapsed_seconds=result.elapsed_seconds,
            )
            with record.condition:
                record.completed_directory = result.run_directory
                self._publish_locked(
                    record,
                    RunState.COMPLETED,
                    "Analysis completed",
                    stats={
                        "schemas": summary.schemas_analyzed,
                        "tables": summary.tables,
                        "columns": summary.columns,
                        "candidates_generated": summary.candidates_generated,
                        "candidates_validated": summary.candidates_validated,
                        "candidates_skipped": summary.candidates_skipped,
                        "relationships_in_report": summary.relationships_in_report,
                    },
                    summary=summary,
                )
        except AnalysisCancelled:
            with record.condition:
                self._publish_locked(record, RunState.CANCELLED, "Analysis cancelled safely")
        except AnalysisExecutionError as exc:
            with record.condition:
                self._publish_locked(
                    record,
                    RunState.FAILED,
                    exc.message,
                    error_code=exc.code,
                )
        except Exception as exc:  # noqa: BLE001 - final safe background-job boundary.
            LOGGER.error(
                "Unexpected analysis run failure (run=%s, type=%s)",
                record.run_id,
                type(exc).__name__,
            )
            with record.condition:
                self._publish_locked(
                    record,
                    RunState.FAILED,
                    "Unexpected analysis failure.",
                    error_code="UNEXPECTED_ANALYSIS_FAILURE",
                )
        finally:
            self.sessions.release_from_run(record.connection_id)
            with self._lock:
                self._active_by_connection.pop(record.connection_id, None)

    def _progress(self, record: _RunRecord, progress: AnalysisProgress) -> None:
        state = RunState(progress.phase.value)
        with record.condition:
            if record.latest.state in TERMINAL_STATES | {RunState.CANCEL_REQUESTED}:
                return
            current_order = PHASE_ORDER.get(record.latest.state, -1)
            next_order = PHASE_ORDER[state]
            if next_order < current_order:
                raise RuntimeError("Analysis progress moved backwards")
            self._publish_locked(
                record,
                state,
                progress.message,
                current=progress.current,
                total=progress.total,
                stats=progress.stats,
            )

    def _publish_locked(
        self,
        record: _RunRecord,
        state: RunState,
        message: str,
        *,
        current: int | None = None,
        total: int | None = None,
        stats: dict[str, int] | None = None,
        summary: RunSummary | None = None,
        error_code: str | None = None,
    ) -> None:
        event = RunProgressEvent(
            sequence=record.latest.sequence + 1,
            run_id=record.run_id,
            state=state,
            message=message,
            current=current,
            total=total,
            stats=_safe_stats(stats),
            summary=summary,
            error_code=error_code,
        )
        record.latest = event
        record.events.append(event)
        record.condition.notify_all()

    def _record(self, run_id: str) -> _RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            raise ApiProblem(404, "RUN_NOT_FOUND", "The analysis run was not found.")
        return record

    def _trim_runs_locked(self) -> None:
        if len(self._runs) < self.max_runs:
            return
        terminal = [item for item in self._runs.values() if item.latest.state in TERMINAL_STATES]
        if terminal:
            oldest = min(terminal, key=lambda item: item.events[-1].sequence)
            self._runs.pop(oldest.run_id, None)


def _safe_stats(values: dict[str, int] | None) -> dict[str, int]:
    if not values:
        return {}
    return {
        key: int(value)
        for key, value in values.items()
        if key in SAFE_STATS and isinstance(value, int) and not isinstance(value, bool)
    }


def _core_config(
    schemas: tuple[str, ...],
    values: AnalysisConfiguration,
    output_root: Path,
) -> AppConfig:
    return AppConfig(
        database=DatabaseConfig("runtime-session", 1521, "runtime", "runtime", "UNUSED"),
        schemas=schemas,
        analysis=AnalysisConfig(
            metadata_candidate_threshold=values.metadata_candidate_threshold,
            min_report_confidence=values.min_report_confidence,
        ),
        sampling=SamplingConfig(
            enabled=values.sampling_enabled,
            max_source_rows=values.max_source_rows,
            max_target_rows=values.max_target_rows,
            bind_batch_size=values.bind_batch_size,
            mode=values.sampling_mode,
        ),
        performance=PerformanceConfig(
            max_workers=values.max_workers,
            candidate_validation_limit=values.candidate_validation_limit,
            query_timeout_seconds=values.query_timeout_seconds,
        ),
        output=OutputConfig(directory=output_root),
        erd=ErdConfig(
            enabled=True,
            min_confidence=values.erd_min_confidence,
            scope=values.erd_scope,
            exclude_generic=values.erd_exclude_generic,
        ),
    )


def _safe_execution_error(exc: Exception) -> AnalysisExecutionError:
    value = str(exc).upper()
    if "ORA-01013" in value or "CANCEL" in value:
        return AnalysisExecutionError("ANALYSIS_CANCELLED", "Analysis was cancelled safely.")
    if "ORA-12170" in value or "TIMEOUT" in value:
        return AnalysisExecutionError("ANALYSIS_TIMEOUT", "Analysis timed out.")
    if any(code in value for code in ("ORA-03113", "ORA-03114", "DPY-1001", "DPY-4011")):
        return AnalysisExecutionError("ORACLE_CONNECTION_LOST", "Oracle connection was lost.")
    if any(name in value for name in ("ALL_TABLES", "ALL_TAB_COLUMNS", "ALL_CONSTRAINTS")):
        return AnalysisExecutionError("METADATA_ACCESS_FAILED", "Oracle metadata access failed.")
    return AnalysisExecutionError(
        "UNEXPECTED_ANALYSIS_FAILURE",
        "Unexpected analysis failure.",
    )
