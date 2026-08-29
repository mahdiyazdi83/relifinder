"""Conservative, deterministic Oracle identifier similarity."""

from __future__ import annotations

import re
from dataclasses import dataclass

from oracle_relationship_discovery.models import ColumnMetadata

IDENTIFIER_SUFFIXES = ("ID", "KEY", "CODE", "NO", "NUMBER")
TABLE_PREFIXES = {"T", "TB", "TBL", "TABLE", "V", "VW", "VIEW"}


def tokenize(identifier: str) -> tuple[str, ...]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", identifier.strip())
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).upper().strip("_")
    tokens = tuple(token for token in value.split("_") if token)
    if len(tokens) == 1:
        compact = tokens[0]
        for suffix in IDENTIFIER_SUFFIXES:
            if compact.endswith(suffix) and len(compact) > len(suffix):
                return (compact[: -len(suffix)], suffix)
    return tokens


def semantic_root(identifier: str) -> str:
    tokens = list(tokenize(identifier))
    while tokens and tokens[-1] in IDENTIFIER_SUFFIXES:
        tokens.pop()
    return "_".join(tokens)


def table_semantic_root(identifier: str) -> str:
    """Remove conventional physical prefixes before comparing a table to a column entity."""
    tokens = list(tokenize(identifier))
    if len(tokens) > 1 and tokens[0] in TABLE_PREFIXES:
        tokens.pop(0)
    return "_".join(tokens)


def _entity_key(value: str) -> str:
    return value.replace("_", "")


def is_identifier_like(identifier: str) -> bool:
    tokens = tokenize(identifier)
    return bool(tokens and tokens[-1] in IDENTIFIER_SUFFIXES)


@dataclass(frozen=True, slots=True)
class NameEvidence:
    ratio: float
    explanation: str
    entity: str = ""


def compare_names(
    source: ColumnMetadata,
    target: ColumnMetadata,
    generic_entities: set[str] | frozenset[str] = frozenset(),
) -> NameEvidence:
    """Return a 0..1 semantic score; generic names require extra evidence."""
    source_root = semantic_root(source.name)
    target_root = semantic_root(target.name)
    target_table_root = table_semantic_root(target.table)
    source_tokens = set(tokenize(source.name))
    target_tokens = set(tokenize(target.name))
    entity = source_root or target_root or target_table_root

    source_entity = _entity_key(source_root)
    target_entity = _entity_key(target_root)
    table_entity = _entity_key(target_table_root)

    if source_entity and source_entity == table_entity and target.name.upper() in {"ID", "KEY"}:
        ratio, reason = 1.0, "source column names the target table and points to its identifier"
    elif source.name.upper() == target.name.upper() and source_entity == table_entity:
        ratio, reason = 0.96, "column names match and align with the target table"
    elif source_entity and source_entity == target_entity:
        ratio, reason = 0.86, "source and target identifier roots match"
    elif source.name.upper() == target.name.upper():
        ratio, reason = 0.68, "column names match but table semantics are weak"
    elif source_tokens & target_tokens and is_identifier_like(source.name):
        ratio, reason = 0.55, "identifier names share semantic tokens"
    else:
        ratio, reason = 0.0, "identifier names do not provide semantic evidence"

    if entity in generic_entities or source_root in generic_entities:
        ratio *= 0.62
        reason += "; generic entity name was conservatively penalized"
    if source.table == target.table and source.schema == target.schema:
        ratio = 0.0
        reason = "self-table column pairs are not inferred in this version"
    return NameEvidence(round(ratio, 4), reason, entity)
