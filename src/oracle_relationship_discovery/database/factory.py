"""Composition root for selecting the configured database provider."""

from oracle_relationship_discovery.database.base import DatabaseAdapter, DatabaseSettings

SUPPORTED_DATABASE_TYPES = ("oracle", "postgresql", "mysql", "mariadb")


def adapter_for(config: DatabaseSettings) -> DatabaseAdapter:
    if config.type == "oracle":
        from oracle_relationship_discovery.providers.oracle import ORACLE_ADAPTER

        return ORACLE_ADAPTER
    if config.type == "postgresql":
        from oracle_relationship_discovery.providers.postgresql import POSTGRESQL_ADAPTER

        return POSTGRESQL_ADAPTER
    if config.type == "mysql":
        from oracle_relationship_discovery.providers.mysql import MYSQL_ADAPTER

        return MYSQL_ADAPTER
    if config.type == "mariadb":
        from oracle_relationship_discovery.providers.mysql import MARIADB_ADAPTER

        return MARIADB_ADAPTER
    raise ValueError(f"Unsupported database type: {config.type!r}")
