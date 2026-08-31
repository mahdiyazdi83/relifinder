"""Oracle connection creation and strict SELECT-only execution helpers."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from oracle_relationship_discovery.config import DatabaseConfig

IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_$#]{0,127}$")
SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
FORBIDDEN_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|BEGIN|DECLARE|CALL|EXECUTE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def quote_identifier(identifier: str) -> str:
    """Quote a metadata identifier after conservative validation."""
    normalized = identifier.upper()
    if not IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"Unsupported or unsafe Oracle identifier: {identifier!r}")
    return f'"{normalized}"'


def assert_select_only(sql: str) -> None:
    without_literals = re.sub(r"'[^']*'", "''", sql)
    if not SELECT_RE.match(without_literals) or FORBIDDEN_SQL_RE.search(without_literals):
        raise ValueError("Only SELECT statements are allowed")
    # Semicolons are unnecessary with the driver and can hide additional statements.
    if ";" in without_literals:
        raise ValueError("SQL statement terminators are not allowed")


def execute_select(
    cursor: Any, sql: str, binds: Mapping[str, Any] | Sequence[Any] | None = None
) -> Any:
    assert_select_only(sql)
    cursor.execute(sql, binds or {})
    return cursor


@contextmanager
def connect(config: DatabaseConfig, timeout_seconds: int) -> Iterator[Any]:
    """Open an Oracle connection; call_timeout is a client-side cancellation guard."""
    with connect_with_credentials(
        host=config.host,
        port=config.port,
        service_name=config.service_name,
        username=config.username,
        password=config.password(),
        timeout_seconds=timeout_seconds,
    ) as connection:
        yield connection


@contextmanager
def connect_with_credentials(
    *,
    host: str,
    port: int,
    service_name: str,
    username: str,
    password: str,
    timeout_seconds: int,
) -> Iterator[Any]:
    """Open a bounded direct connection for runtime-only GUI credentials."""
    import oracledb

    dsn = oracledb.makedsn(host, port, service_name=service_name)
    connection = oracledb.connect(user=username, password=password, dsn=dsn)
    connection.call_timeout = timeout_seconds * 1000
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def connection_pool(
    config: DatabaseConfig, timeout_seconds: int, max_connections: int
) -> Iterator[Callable[[], Any]]:
    """Yield a context-manager factory backed by a small, fixed-size Oracle pool."""
    import oracledb

    dsn = oracledb.makedsn(config.host, config.port, service_name=config.service_name)
    pool = oracledb.create_pool(
        user=config.username,
        password=config.password(),
        dsn=dsn,
        min=1,
        max=max_connections,
        increment=1,
        getmode=oracledb.POOL_GETMODE_WAIT,
    )

    @contextmanager
    def acquire() -> Iterator[Any]:
        connection = pool.acquire()
        connection.call_timeout = timeout_seconds * 1000
        try:
            yield connection
        finally:
            pool.release(connection)

    try:
        yield acquire
    finally:
        pool.close(force=True)
