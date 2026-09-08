"""PostgreSQL provider for ReliFinder."""

from oracle_relationship_discovery.providers.postgresql.adapter import PostgreSQLAdapter

POSTGRESQL_ADAPTER = PostgreSQLAdapter()

__all__ = ["POSTGRESQL_ADAPTER", "PostgreSQLAdapter"]
