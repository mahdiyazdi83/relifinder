"""PostgreSQL connection lifecycle and identifier safety."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from oracle_relationship_discovery.config import DatabaseConfig
from oracle_relationship_discovery.database.base import DatabaseError
from oracle_relationship_discovery.providers.dbapi import (
    DbApiRuntimePool,
    execute_read,
    validate_identifier,
)


def quote_identifier(identifier: str) -> str:
    value = validate_identifier(
        identifier, dialect="PostgreSQL", max_length=63, length_in_bytes=True
    )
    return '"' + value.replace('"', '""') + '"'


def _connect(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: int,
) -> Any:
    try:
        import psycopg
    except ImportError:
        raise DatabaseError(
            "DRIVER_MISSING",
            "PostgreSQL support requires the 'postgres' extra.",
            status_code=400,
        ) from None
    return psycopg.connect(
        host=host,
        port=port,
        dbname=database,
        user=username,
        password=password,
        connect_timeout=timeout_seconds,
        options=(
            f"-c statement_timeout={timeout_seconds * 1000} -c default_transaction_read_only=on"
        ),
        application_name="ReliFinder",
    )


def create_pool_with_credentials(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: int = 15,
    max_connections: int = 8,
) -> DbApiRuntimePool:
    def factory() -> Any:
        return _connect(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
        )

    return DbApiRuntimePool(factory, max_connections, "PostgreSQL")


@contextmanager
def connection_pool(
    config: DatabaseConfig, timeout_seconds: int, max_connections: int
) -> Iterator[Callable[[], Any]]:
    resource = create_pool_with_credentials(
        host=config.host,
        port=config.port,
        database=config.database_name,
        username=config.username,
        password=config.password(),
        timeout_seconds=timeout_seconds,
        max_connections=max_connections,
    )

    def acquire():
        return resource.acquire(timeout_seconds)

    try:
        yield acquire
    finally:
        resource.close()


__all__ = [
    "connection_pool",
    "create_pool_with_credentials",
    "execute_read",
    "quote_identifier",
]
