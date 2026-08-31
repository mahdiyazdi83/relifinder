"""Validated YAML and environment based configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WEIGHTS = {
    "name": 35,
    "datatype": 15,
    "target_key": 15,
    "overlap": 25,
    "consistency": 5,
    "structure": 5,
}
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str
    port: int
    service_name: str
    username: str
    password_env: str

    def password(self) -> str:
        value = os.environ.get(self.password_env)
        if not value:
            raise ValueError(
                f"Required password environment variable is not set: {self.password_env}"
            )
        return value


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    metadata_candidate_threshold: float = 40
    min_report_confidence: float = 40
    generic_entities: tuple[str, ...] = ("STATUS", "TYPE", "USER", "CODE", "CATEGORY", "KIND")
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))


@dataclass(frozen=True, slots=True)
class SamplingConfig:
    enabled: bool = True
    max_source_rows: int = 3000
    max_target_rows: int = 5000
    bind_batch_size: int = 500
    mode: str = "first"


@dataclass(frozen=True, slots=True)
class PerformanceConfig:
    max_workers: int = 2
    candidate_validation_limit: int = 1000
    query_timeout_seconds: int = 15


@dataclass(frozen=True, slots=True)
class OutputConfig:
    directory: Path = Path("output")
    log_file: Path | None = Path("logs/oracle-relationship-discovery.log")


@dataclass(frozen=True, slots=True)
class ErdConfig:
    enabled: bool = False
    format: str = "dbml"
    min_confidence: float = 80
    scope: str = "full"
    schemas: tuple[str, ...] = ()
    max_relationships: int | None = None
    exclude_generic: bool = False


@dataclass(frozen=True, slots=True)
class AppConfig:
    database: DatabaseConfig
    schemas: tuple[str, ...]
    analysis: AnalysisConfig = AnalysisConfig()
    sampling: SamplingConfig = SamplingConfig()
    performance: PerformanceConfig = PerformanceConfig()
    output: OutputConfig = OutputConfig()
    erd: ErdConfig = ErdConfig()


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), match.group(0)), value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _positive(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = _expand_env(yaml.safe_load(handle) or {})
    db = raw.get("database", {})
    required = ("host", "service_name", "username", "password_env")
    missing = [key for key in required if not db.get(key)]
    if missing:
        raise ValueError(f"Missing database settings: {', '.join(missing)}")
    schemas = tuple(dict.fromkeys(str(s).upper() for s in raw.get("schemas", []) if s))
    if not schemas:
        raise ValueError("At least one schema must be configured")

    analysis_raw = raw.get("analysis", {})
    weights = dict(DEFAULT_WEIGHTS)
    weights.update({k: float(v) for k, v in analysis_raw.get("weights", {}).items()})
    if set(weights) != set(DEFAULT_WEIGHTS) or round(sum(weights.values()), 6) != 100:
        raise ValueError(f"Analysis weights must contain {sorted(DEFAULT_WEIGHTS)} and sum to 100")
    sampling_raw = raw.get("sampling", {})
    performance_raw = raw.get("performance", {})
    output_raw = raw.get("output", {})
    erd_raw = raw.get("erd", {})

    erd_format = str(erd_raw.get("format", "dbml")).lower()
    if erd_format != "dbml":
        raise ValueError("erd.format must be 'dbml'")
    erd_scope = str(erd_raw.get("scope", "full")).lower()
    if erd_scope not in {"full", "schema", "cross-schema"}:
        raise ValueError("erd.scope must be 'full', 'schema', or 'cross-schema'")
    erd_min_confidence = float(erd_raw.get("min_confidence", 80))
    if not 0 <= erd_min_confidence <= 100:
        raise ValueError("erd.min_confidence must be between 0 and 100")
    raw_max_relationships = erd_raw.get("max_relationships")
    erd_max_relationships = (
        _positive("erd.max_relationships", int(raw_max_relationships))
        if raw_max_relationships is not None
        else None
    )

    sampling = SamplingConfig(
        enabled=bool(sampling_raw.get("enabled", True)),
        max_source_rows=_positive(
            "max_source_rows", int(sampling_raw.get("max_source_rows", 3000))
        ),
        max_target_rows=_positive(
            "max_target_rows", int(sampling_raw.get("max_target_rows", 5000))
        ),
        bind_batch_size=min(
            1000, _positive("bind_batch_size", int(sampling_raw.get("bind_batch_size", 500)))
        ),
        mode=str(sampling_raw.get("mode", "first")).lower(),
    )
    if sampling.mode not in {"first", "sample"}:
        raise ValueError("sampling.mode must be 'first' or 'sample'")

    log_file = output_raw.get("log_file", "logs/oracle-relationship-discovery.log")
    return AppConfig(
        database=DatabaseConfig(
            host=str(db["host"]),
            port=int(db.get("port", 1521)),
            service_name=str(db["service_name"]),
            username=str(db["username"]),
            password_env=str(db["password_env"]),
        ),
        schemas=schemas,
        analysis=AnalysisConfig(
            metadata_candidate_threshold=float(
                analysis_raw.get("metadata_candidate_threshold", 40)
            ),
            min_report_confidence=float(analysis_raw.get("min_report_confidence", 40)),
            generic_entities=tuple(
                str(v).upper()
                for v in analysis_raw.get("generic_entities", AnalysisConfig().generic_entities)
            ),
            weights=weights,
        ),
        sampling=sampling,
        performance=PerformanceConfig(
            max_workers=min(
                8, _positive("max_workers", int(performance_raw.get("max_workers", 2)))
            ),
            candidate_validation_limit=_positive(
                "candidate_validation_limit",
                int(performance_raw.get("candidate_validation_limit", 1000)),
            ),
            query_timeout_seconds=_positive(
                "query_timeout_seconds", int(performance_raw.get("query_timeout_seconds", 15))
            ),
        ),
        output=OutputConfig(
            directory=Path(output_raw.get("directory", "output")),
            log_file=Path(log_file) if log_file else None,
        ),
        erd=ErdConfig(
            enabled=bool(erd_raw.get("enabled", False)),
            format=erd_format,
            min_confidence=erd_min_confidence,
            scope=erd_scope,
            schemas=tuple(
                dict.fromkeys(str(value).upper() for value in erd_raw.get("schemas", []) if value)
            ),
            max_relationships=erd_max_relationships,
            exclude_generic=bool(erd_raw.get("exclude_generic", False)),
        ),
    )
