"""PostgreSQL bounded validation sampling."""

from oracle_relationship_discovery.config import SamplingConfig
from oracle_relationship_discovery.providers.dbapi import DbApiDataSampler
from oracle_relationship_discovery.providers.postgresql.connection import quote_identifier


class PostgreSQLDataSampler(DbApiDataSampler):
    def __init__(self, connection_factory, sampling: SamplingConfig) -> None:
        super().__init__(
            connection_factory,
            sampling,
            quote_identifier,
            table_sample_clause=" TABLESAMPLE SYSTEM (1)",
        )
