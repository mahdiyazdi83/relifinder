"""MySQL/MariaDB connection lifecycle and identifier safety."""

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
    value = validate_identifier(identifier, dialect="MySQL/MariaDB", max_length=64)
    return "`" + value.replace("`", "``") + "`"


def _connect(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: int,
    mariadb: bool = False,
) -> Any:
    try:
        import pymysql
    except ImportError:
        raise DatabaseError(
            "DRIVER_MISSING",
            "MySQL/MariaDB support requires the 'mysql' extra.",
            status_code=400,
        ) from None
    connection = pymysql.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password,
        connect_timeout=timeout_seconds,
        read_timeout=timeout_seconds,
        write_timeout=timeout_seconds,
        autocommit=False,
        charset="utf8mb4",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            if mariadb:
                cursor.execute("SET SESSION max_statement_time = %s", (timeout_seconds,))
            else:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME = %s", (timeout_seconds * 1000,))
    except Exception:
        connection.close()
        raise
    return connection


def create_pool_with_credentials(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    timeout_seconds: int = 15,
    max_connections: int = 8,
    display_name: str = "MySQL/MariaDB",
    mariadb: bool = False,
) -> DbApiRuntimePool:
    def factory() -> Any:
        return _connect(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
            mariadb=mariadb,
        )

    return DbApiRuntimePool(factory, max_connections, display_name)


@contextmanager
def connection_pool(
    config: DatabaseConfig,
    timeout_seconds: int,
    max_connections: int,
    *,
    display_name: str,
    mariadb: bool = False,
) -> Iterator[Callable[[], Any]]:
    resource = create_pool_with_credentials(
        host=config.host,
        port=config.port,
        database=config.database_name,
        username=config.username,
        password=config.password(),
        timeout_seconds=timeout_seconds,
        max_connections=max_connections,
        display_name=display_name,
        mariadb=mariadb,
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
