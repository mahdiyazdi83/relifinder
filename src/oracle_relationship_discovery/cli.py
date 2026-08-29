"""Command-line orchestration."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from oracle_relationship_discovery.config import load_config
from oracle_relationship_discovery.db.connection import connect, connection_pool
from oracle_relationship_discovery.db.data_sampler import OracleDataSampler
from oracle_relationship_discovery.db.metadata_repository import MetadataRepository
from oracle_relationship_discovery.models import AnalysisStats, ValidationStatus
from oracle_relationship_discovery.output.csv_report import write_csv
from oracle_relationship_discovery.output.html_report import write_html

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover probable logical Oracle relationships safely"
    )
    parser.add_argument("--config", type=Path, required=True, help="YAML configuration path")
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


def run_analyze(args: argparse.Namespace) -> int:
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
    if not 0 <= min_confidence <= 100:
        raise ValueError("--min-confidence must be between 0 and 100")
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

    LOGGER.info("[1/5] Reading metadata for %d configured schemas", len(config.schemas))
    with connect(config.database, config.performance.query_timeout_seconds) as connection:
        tables = MetadataRepository(connection).load(config.schemas)
    columns = sum(len(table.columns) for table in tables)

    LOGGER.info(
        "[2/5] Building metadata candidates from %d tables and %d columns", len(tables), columns
    )
    from oracle_relationship_discovery.analysis.candidate_generator import generate_candidates

    candidates = generate_candidates(
        tables,
        config.analysis.metadata_candidate_threshold,
        config.analysis.weights,
        config.analysis.generic_entities,
    )
    LOGGER.info(
        "[3/5] %d candidates passed metadata threshold %.1f",
        len(candidates),
        config.analysis.metadata_candidate_threshold,
    )

    LOGGER.info("[4/5] Validating candidates with bounded sampling=%s", config.sampling.enabled)
    from oracle_relationship_discovery.analysis.relationship_validator import validate_candidates

    if config.sampling.enabled:
        with connection_pool(
            config.database,
            config.performance.query_timeout_seconds,
            config.performance.max_workers,
        ) as acquire_connection:
            factory = lambda: OracleDataSampler(acquire_connection, config.sampling)
            candidates, skipped_by_limit = validate_candidates(candidates, factory, config)
    else:
        # The factory is deliberately unused by metadata-only validation.
        candidates, skipped_by_limit = validate_candidates(candidates, lambda: None, config)
    report_candidates = [candidate for candidate in candidates if candidate.score >= min_confidence]

    validated = sum(
        candidate.evidence.status == ValidationStatus.VALIDATED for candidate in candidates
    )
    stats = AnalysisStats(
        schemas=len({table.schema for table in tables}),
        tables=len(tables),
        columns=columns,
        candidates_generated=len(candidates),
        candidates_validated=validated,
        candidates_skipped_by_limit=skipped_by_limit,
    )
    LOGGER.info("[5/5] Writing %d relationships to %s", len(report_candidates), run_directory)
    write_csv(run_directory / "relationships.csv", report_candidates, mode, generated_at)
    write_html(
        run_directory / "relationship-report.html",
        report_candidates,
        stats,
        analysis_mode=mode,
        generated_at=generated_at,
    )
    LOGGER.info("RUN COMPLETE: %s", run_directory.name)
    LOGGER.info("Analysis complete. Reports contain aggregate evidence only.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return run_analyze(args)
    except (ValueError, OSError) as exc:
        message = f"error: {exc}"
        if logging.getLogger().handlers:
            LOGGER.error(message)
        else:
            print(message, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - present driver failures without a noisy traceback.
        message = f"database analysis failed ({type(exc).__name__}): {exc}"
        if logging.getLogger().handlers:
            LOGGER.error(message)
        else:
            print(message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 1
