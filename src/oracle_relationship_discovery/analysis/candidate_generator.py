"""Metadata-first candidate generation with indexed semantic lookup."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from oracle_relationship_discovery.analysis.datatype import compare_datatypes, datatype_family
from oracle_relationship_discovery.analysis.name_similarity import (
    compare_names,
    is_identifier_like,
    semantic_root,
)
from oracle_relationship_discovery.analysis.scorer import preliminary_breakdown
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    RelationshipCandidate,
    TableMetadata,
)


def _structure_ratio(source: ColumnMetadata, target: ColumnMetadata) -> float:
    ratio = 0.0
    if not target.nullable:
        ratio += 0.4
    if source.schema == target.schema:
        ratio += 0.15
    if source.num_distinct and target.num_distinct and source.num_distinct <= target.num_distinct:
        ratio += 0.45
    return min(1.0, ratio)


def generate_candidates(
    tables: Iterable[TableMetadata],
    threshold: float,
    weights: dict[str, float],
    generic_entities: Iterable[str],
) -> list[RelationshipCandidate]:
    columns = [column for table in tables for column in table.columns]
    generic = frozenset(value.upper() for value in generic_entities)
    target_index: dict[tuple[str, str], list[ColumnMetadata]] = defaultdict(list)

    for target in columns:
        if target.composite_constraints:
            continue  # Never treat one composite-key component as a complete unique target.
        if not (target.is_single_column_key or is_identifier_like(target.name)):
            continue
        family = datatype_family(target.data_type)
        keys = {semantic_root(target.name), semantic_root(target.table), target.name.upper()}
        for key in filter(None, keys):
            target_index[(family, key)].append(target)

    candidates: dict[tuple[str, str], RelationshipCandidate] = {}
    for source in columns:
        if not is_identifier_like(source.name):
            continue
        family = datatype_family(source.data_type)
        lookup_keys = {semantic_root(source.name), source.name.upper()}
        possible: dict[str, ColumnMetadata] = {}
        for key in filter(None, lookup_keys):
            for target in target_index.get((family, key), []):
                possible[target.qualified_name] = target
        for target in possible.values():
            if source.qualified_name == target.qualified_name:
                continue
            names = compare_names(source, target, generic)
            if names.ratio <= 0:
                continue
            datatypes = compare_datatypes(source, target)
            if not datatypes.compatible:
                continue
            preliminary = preliminary_breakdown(
                names.ratio,
                datatypes.ratio,
                target.key_type,
                weights,
                _structure_ratio(source, target),
            )
            if preliminary.total < threshold:
                continue
            reasons = [names.explanation, datatypes.explanation]
            if target.is_single_column_key:
                reasons.append(f"target is a declared {target.key_type.value.lower()}")
            else:
                reasons.append(
                    "target has no declared single-column key; uniqueness needs sampling"
                )
            key = (source.qualified_name, target.qualified_name)
            candidates[key] = RelationshipCandidate(source, target, preliminary, reasons)
    return sorted(
        candidates.values(),
        key=lambda item: (
            -item.preliminary.total,
            item.source.qualified_name,
            item.target.qualified_name,
        ),
    )
