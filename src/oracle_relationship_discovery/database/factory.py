"""Composition root for selecting the configured database provider."""

from oracle_relationship_discovery.database.base import DatabaseAdapter, DatabaseSettings


def adapter_for(config: DatabaseSettings) -> DatabaseAdapter:
    if config.type == "oracle":
        from oracle_relationship_discovery.providers.oracle import ORACLE_ADAPTER

        return ORACLE_ADAPTER
    raise ValueError(f"Unsupported database type: {config.type!r}")
