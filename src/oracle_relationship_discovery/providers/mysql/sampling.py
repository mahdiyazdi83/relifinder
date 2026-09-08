"""MySQL/MariaDB bounded validation sampling."""

from oracle_relationship_discovery.config import SamplingConfig
from oracle_relationship_discovery.providers.dbapi import DbApiDataSampler
from oracle_relationship_discovery.providers.mysql.connection import quote_identifier


class MySQLDataSampler(DbApiDataSampler):
    def __init__(self, connection_factory, sampling: SamplingConfig) -> None:
        # Neither MySQL nor MariaDB offers a portable low-cost TABLESAMPLE clause.
        # Both modes therefore use the same bounded LIMIT contract without random sorting.
        super().__init__(connection_factory, sampling, quote_identifier)
