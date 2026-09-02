from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from oracle_relationship_discovery.gui.errors import ApiProblem
from oracle_relationship_discovery.gui.schemas.artifacts import (
    ArtifactListResponse,
    ArtifactMetadata,
)
from oracle_relationship_discovery.gui.services.runs import CompletedRun, RunService

_CSV_HEADER = "analysis_mode,report_generated_at,source_schema,source_table,source_column,"
_DBML_FIELDS = {
    "Minimum confidence": "min_confidence",
    "Scope": "scope",
    "Eligible after filters/limit": "eligible_relationships",
    "Rendered DBML references": "rendered_relationships",
    "Unknown cardinality omitted": "unknown_cardinality_omitted",
}
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class ResolvedArtifact:
    metadata: ArtifactMetadata
    path: Path
    media_type: str


class ArtifactService:
    """Resolve a small, run-owned allowlist of completed output artifacts."""

    def __init__(self, runs: RunService) -> None:
        self.runs = runs

    def list(self, run_id: str) -> ArtifactListResponse:
        completed = self.runs.completed(run_id)
        manifest = self._manifest(completed)
        return ArtifactListResponse(
            run_id=run_id,
            artifacts=tuple(item.metadata for item in manifest.values()),
        )

    def resolve(self, run_id: str, artifact_id: str) -> ResolvedArtifact:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", artifact_id):
            raise _not_found()
        completed = self.runs.completed(run_id)
        item = self._manifest(completed).get(artifact_id)
        if item is None:
            raise _not_found()
        if not item.metadata.available:
            raise ApiProblem(
                409,
                "ARTIFACT_UNAVAILABLE",
                "The requested artifact was not generated as a valid completed output.",
            )
        return item

    def _manifest(self, completed: CompletedRun) -> dict[str, ResolvedArtifact]:
        root = completed.run_directory.resolve()
        manifest: dict[str, ResolvedArtifact] = {}
        manifest["relationships-csv"] = self._fixed_artifact(
            root,
            "relationships-csv",
            "csv",
            "relationships.csv",
            "text/csv; charset=utf-8",
            _valid_csv,
        )
        manifest["analysis-html"] = self._fixed_artifact(
            root,
            "analysis-html",
            "html",
            "relationship-report.html",
            "text/html; charset=utf-8",
            _valid_html,
        )

        dbml_root = root / "erd"
        dbml_paths = []
        try:
            resolved_dbml_root = dbml_root.resolve()
        except OSError:
            resolved_dbml_root = root / ".invalid-erd-root"
        if dbml_root.is_dir() and resolved_dbml_root.parent == root:
            for candidate in dbml_root.rglob("*.dbml"):
                try:
                    resolved = candidate.resolve(strict=True)
                except OSError:
                    continue
                if resolved.is_file() and resolved.is_relative_to(resolved_dbml_root):
                    dbml_paths.append(resolved)
        dbml_paths.sort(key=lambda path: path.relative_to(resolved_dbml_root).as_posix())
        for index, path in enumerate(dbml_paths):
            relative_name = path.relative_to(resolved_dbml_root).as_posix()
            artifact_id = (
                "erd-dbml"
                if len(dbml_paths) == 1
                else "erd-dbml-" + hashlib.sha256(relative_name.encode()).hexdigest()[:16]
            )
            metadata_values = _dbml_metadata(path)
            valid = metadata_values is not None
            metadata = ArtifactMetadata(
                id=artifact_id,
                type="dbml",
                filename=path.name
                if _SAFE_FILENAME.fullmatch(path.name)
                else f"erd-{index + 1}.dbml",
                available=valid,
                size_bytes=path.stat().st_size if valid else None,
                scope=(metadata_values or {}).get("scope", completed.erd_scope),
                min_confidence=(metadata_values or {}).get(
                    "min_confidence", completed.erd_min_confidence
                ),
                eligible_relationships=(metadata_values or {}).get("eligible_relationships"),
                rendered_relationships=(metadata_values or {}).get("rendered_relationships"),
                unknown_cardinality_omitted=(metadata_values or {}).get(
                    "unknown_cardinality_omitted"
                ),
            )
            manifest[artifact_id] = ResolvedArtifact(metadata, path, "text/plain; charset=utf-8")
        if not dbml_paths:
            filename = "cross-schema.dbml" if completed.erd_scope == "cross-schema" else "full.dbml"
            manifest["erd-dbml"] = ResolvedArtifact(
                ArtifactMetadata(
                    id="erd-dbml",
                    type="dbml",
                    filename=filename,
                    available=False,
                    scope=completed.erd_scope,
                    min_confidence=completed.erd_min_confidence,
                ),
                dbml_root / filename,
                "text/plain; charset=utf-8",
            )
        return manifest

    def _fixed_artifact(
        self,
        root: Path,
        artifact_id: str,
        artifact_type: Literal["csv", "html"],
        filename: str,
        media_type: str,
        validator: Callable[[Path], bool],
    ) -> ResolvedArtifact:
        candidate = root / filename
        valid = False
        resolved = candidate
        try:
            resolved = candidate.resolve(strict=True)
            valid = resolved.is_file() and resolved.parent == root and validator(resolved)
        except OSError:
            valid = False
        metadata = ArtifactMetadata(
            id=artifact_id,
            type=artifact_type,
            filename=filename,
            available=valid,
            size_bytes=resolved.stat().st_size if valid else None,
        )
        return ResolvedArtifact(metadata, resolved, media_type)


def _read_prefix(path: Path, limit: int = 16_384) -> str:
    with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
        return handle.read(limit)


def _valid_csv(path: Path) -> bool:
    try:
        return path.stat().st_size > 0 and _read_prefix(path).startswith(_CSV_HEADER)
    except (OSError, UnicodeError):
        return False


def _valid_html(path: Path) -> bool:
    try:
        prefix = _read_prefix(path, 4096).lstrip().lower()
        return path.stat().st_size > 0 and prefix.startswith("<!doctype html") and "<html" in prefix
    except (OSError, UnicodeError):
        return False


def _dbml_metadata(path: Path) -> dict[str, str | float | int] | None:
    try:
        if path.stat().st_size <= 0:
            return None
        prefix = _read_prefix(path)
        if "Generated by ReliFinder" not in prefix or "Project ReliFinder_ERD" not in prefix:
            return None
        values: dict[str, str | float | int] = {}
        for label, key in _DBML_FIELDS.items():
            match = re.search(rf"^// {re.escape(label)}:\s*(.+)$", prefix, re.MULTILINE)
            if not match:
                continue
            raw = match.group(1).strip()
            if key == "scope":
                values[key] = raw
            elif key == "min_confidence":
                values[key] = float(raw)
            else:
                values[key] = int(raw)
        return values
    except (OSError, UnicodeError, ValueError):
        return None


def _not_found() -> ApiProblem:
    return ApiProblem(404, "ARTIFACT_NOT_FOUND", "The requested run artifact was not found.")
