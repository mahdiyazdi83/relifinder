"""Command-line orchestration."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from oracle_relationship_discovery.analysis.service import AnalysisProgress, run_analysis
from oracle_relationship_discovery.config import AnalysisConfig, AppConfig, load_config
from oracle_relationship_discovery.models import ValidationStatus
from oracle_relationship_discovery.output.erd_builder import (
    load_erd_model,
    resolve_offline_source,
)
from oracle_relationship_discovery.output.erd_models import ErdExportOptions
from oracle_relationship_discovery.output.erd_service import export_erd

LOGGER = logging.getLogger(__name__)
ERD_SCOPES = ("full", "schema", "cross-schema")


def _add_erd_arguments(parser: argparse.ArgumentParser, *, analyze: bool) -> None:
    if analyze:
        parser.add_argument("--erd", action="store_true", help="Export an inferred DBML ERD")
    parser.add_argument("--erd-format" if analyze else "--format", choices=("dbml",), default=None)
    parser.add_argument(
        "--erd-min-confidence" if analyze else "--min-confidence",
        type=float,
        default=None if analyze else 80,
        help="Minimum confidence included in ERD exports",
    )
    parser.add_argument(
        "--erd-scope" if analyze else "--scope",
        choices=ERD_SCOPES,
        default=None if analyze else "full",
    )
    parser.add_argument(
        "--erd-schema" if analyze else "--schema",
        action="append",
        default=None,
        metavar="SCHEMA",
        help="Limit ERD export to a schema; repeat for multiple schemas",
    )
    parser.add_argument(
        "--erd-max-relationships" if analyze else "--max-relationships",
        type=int,
        default=None,
        help="Keep only the highest-confidence relationships",
    )
    parser.add_argument(
        "--erd-validation-status" if analyze else "--validation-status",
        action="append",
        choices=tuple(status.value for status in ValidationStatus),
        default=None,
        metavar="STATUS",
        help="Allowed validation status; repeat to allow multiple statuses",
    )
    parser.add_argument(
        "--erd-include-isolated-tables" if analyze else "--include-isolated-tables",
        action="store_true",
        default=None,
        help="Include tables with no qualifying relationship (not for cross-schema scope)",
    )
    parser.add_argument(
        "--erd-exclude-generic" if analyze else "--exclude-generic",
        action="store_true",
        help="Exclude generic entities configured for scoring",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover probable logical Oracle relationships safely"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="YAML configuration path (required for analyze)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Run relationship analysis")
    analyze.add_argument(
        "--metadata-only", action="store_true", help="Do not query user table data"
    )
    analyze.add_argument(
        "--disable-sampling", action="store_true", help="Alias for --metadata-only"
    )
    analyze.add_argument("--min-confidence", type=float, help="Minimum score written to reports")
    analyze.add_argument("--output-dir", type=Path, help="Override report directory")
    analyze.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    _add_erd_arguments(analyze, analyze=True)

    offline = subparsers.add_parser(
        "export-erd",
        help="Export DBML from an existing ReliFinder run without connecting to Oracle",
    )
    offline.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Run directory, analysis-results.json, or legacy relationships.csv",
    )
    offline.add_argument(
        "--metadata",
        type=Path,
        help="Safe schema-metadata.json (defaults to the input artifact directory)",
    )
    offline.add_argument("--output-dir", type=Path, help="ERD destination directory")
    offline.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    _add_erd_arguments(offline, analyze=False)
    return parser


def create_run_directory(base_directory: Path, mode: str, started_at: datetime) -> Path:
    """Create a collision-resistant, human-readable directory for one immutable run."""
    timestamp = started_at.strftime("%Y-%m-%d_%H-%M-%S-%f_%z")
    run_directory = base_directory.resolve() / f"{timestamp}_{mode}"
    run_directory.mkdir(parents=True, exist_ok=False)
    return run_directory


def configure_logging(verbose: bool, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def _validate_percentage(name: str, value: float) -> float:
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return value


def _erd_options(args: argparse.Namespace, config: AppConfig | None = None) -> ErdExportOptions:
    configured = config.erd if config else None
    prefix = "erd_" if config else ""
    minimum = getattr(args, f"{prefix}min_confidence")
    maximum = getattr(args, f"{prefix}max_relationships")
    schemas = getattr(args, f"{prefix}schema") or (configured.schemas if configured else ())
    validation_statuses = getattr(args, f"{prefix}validation_status") or (
        configured.validation_statuses if configured else ("VALIDATED", "NOT_RUN", "SKIPPED")
    )
    include_isolated = getattr(args, f"{prefix}include_isolated_tables")
    if maximum is not None and maximum <= 0:
        flag = "--erd-max-relationships" if config else "--max-relationships"
        raise ValueError(f"{flag} must be greater than zero")
    minimum = minimum if minimum is not None else configured.min_confidence
    _validate_percentage(
        "--erd-min-confidence" if config else "--min-confidence",
        minimum,
    )
    return ErdExportOptions(
        format=getattr(args, f"{prefix}format") or (configured.format if configured else "dbml"),
        scope=getattr(args, f"{prefix}scope") or (configured.scope if configured else "full"),
        min_confidence=minimum,
        schemas=tuple(dict.fromkeys(str(value).upper() for value in schemas)),
        max_relationships=maximum
        if maximum is not None
        else (configured.max_relationships if configured else None),
        exclude_generic=bool(getattr(args, f"{prefix}exclude_generic"))
        or (configured.exclude_generic if configured else False),
        generic_entities=config.analysis.generic_entities
        if config
        else AnalysisConfig().generic_entities,
        include_isolated_tables=include_isolated
        if include_isolated is not None
        else (configured.include_isolated_tables if configured else False),
        validation_statuses=tuple(dict.fromkeys(validation_statuses)),
    )


def run_analyze(args: argparse.Namespace) -> int:
    if args.config is None:
        raise ValueError("--config is required for analyze")
    config = load_config(args.config)
    if args.metadata_only or args.disable_sampling:
        config = replace(config, sampling=replace(config.sampling, enabled=False))
    if args.output_dir:
        config = replace(config, output=replace(config.output, directory=args.output_dir))
    min_confidence = (
        args.min_confidence
        if args.min_confidence is not None
        else config.analysis.min_report_confidence
    )
    _validate_percentage("--min-confidence", min_confidence)
    config = replace(
        config,
        analysis=replace(config.analysis, min_report_confidence=min_confidence),
    )
    erd_options = _erd_options(args, config)
    config = replace(
        config,
        erd=replace(
            config.erd,
            enabled=bool(args.erd or config.erd.enabled),
            format=erd_options.format,
            min_confidence=erd_options.min_confidence,
            scope=erd_options.scope,
            schemas=erd_options.schemas,
            max_relationships=erd_options.max_relationships,
            exclude_generic=erd_options.exclude_generic,
            include_isolated_tables=erd_options.include_isolated_tables,
            validation_statuses=erd_options.validation_statuses,
        ),
    )

    started_at = datetime.now().astimezone()
    mode = "sampled" if config.sampling.enabled else "metadata-only"
    run_directory = create_run_directory(config.output.directory, mode, started_at)
    comprehensive_log = (
        config.output.log_file or Path("logs/oracle-relationship-discovery.log")
    ).resolve()
    configure_logging(args.verbose, comprehensive_log)
    generated_at = started_at.isoformat(timespec="microseconds")

    LOGGER.info("=" * 72)
    LOGGER.info("RUN START: %s", run_directory.name)
    LOGGER.info("Run mode: %s", mode)
    LOGGER.info("Run artifacts: %s", run_directory)
    LOGGER.info("Comprehensive log: %s", comprehensive_log)

    def report_progress(progress: AnalysisProgress) -> None:
        suffix = ""
        if progress.current is not None and progress.total is not None:
            suffix = f" ({progress.current}/{progress.total})"
        LOGGER.info("%s%s", progress.message, suffix)

    run_analysis(
        config,
        run_directory,
        progress_callback=report_progress,
        generated_at=generated_at,
    )
    LOGGER.info("RUN COMPLETE: %s", run_directory.name)
    LOGGER.info("Analysis complete. Reports contain aggregate evidence only.")
    return 0


def run_export_erd(args: argparse.Namespace) -> int:
    requested_input = args.input.resolve()
    source = resolve_offline_source(requested_input)
    run_directory = source.path.parent
    metadata_path = (
        args.metadata.resolve() if args.metadata else run_directory / "schema-metadata.json"
    )
    if args.metadata and not metadata_path.is_file():
        raise ValueError(f"Metadata file does not exist: {metadata_path}")
    if not metadata_path.is_file():
        metadata_path = None

    destination = args.output_dir.resolve() if args.output_dir else run_directory / "erd"
    configure_logging(
        args.verbose,
        Path("logs/oracle-relationship-discovery.log").resolve(),
    )
    LOGGER.info("Offline ERD export source: %s", source.path)
    if source.legacy_csv:
        LOGGER.warning(
            "Using legacy relationships.csv fallback. Relationships below the "
            "original report threshold are unavailable; lowering the ERD "
            "threshold may not restore them."
        )
    if metadata_path:
        LOGGER.info("Using safe metadata artifact %s", metadata_path)
    else:
        LOGGER.warning("schema-metadata.json not found; exporting minimal table definitions")

    results = export_erd(
        load_erd_model(source.path, metadata_path),
        destination,
        _erd_options(args),
    )
    for result in results:
        LOGGER.info(
            "ERD written: %s (eligible=%d, rendered=%d, unknown_omitted=%d, "
            "limit_omitted=%d, validation_omitted=%d)",
            result.path,
            result.eligible_relationships,
            result.rendered_relationships,
            result.unknown_cardinality_relationships,
            result.omitted_by_limit,
            result.omitted_by_validation_filter,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return run_analyze(args)
        if args.command == "export-erd":
            return run_export_erd(args)
    except (ValueError, OSError) as exc:
        message = f"error: {exc}"
        if logging.getLogger().handlers:
            LOGGER.error(message)
        else:
            print(message, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - present driver failures without a noisy traceback.
        message = f"operation failed ({type(exc).__name__}): {exc}"
        if logging.getLogger().handlers:
            LOGGER.error(message)
        else:
            print(message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 1
