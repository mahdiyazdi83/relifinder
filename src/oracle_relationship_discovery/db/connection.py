"""Backward-compatible imports for the Oracle provider connection helpers."""

from oracle_relationship_discovery.providers.oracle.connection import (
    RuntimeOraclePool,
    assert_select_only,
    connect,
    connect_with_credentials,
    connection_pool,
    create_pool_with_credentials,
    execute_select,
    quote_identifier,
)

__all__ = [
    "RuntimeOraclePool",
    "assert_select_only",
    "connect",
    "connect_with_credentials",
    "connection_pool",
    "create_pool_with_credentials",
    "execute_select",
    "quote_identifier",
]
