"""Opt-in live adapter smoke tests; no database objects are created or changed."""

from __future__ import annotations

import os

import pytest

from oracle_relationship_discovery.database.factory import adapter_for


@pytest.mark.integration
@pytest.mark.parametrize(
    ("database_type", "prefix", "default_port"),
    [
        ("postgresql", "RELIFINDER_POSTGRES", 5432),
        ("mysql", "RELIFINDER_MYSQL", 3306),
        ("mariadb", "RELIFINDER_MARIADB", 3306),
    ],
)
def test_live_provider_read_only_metadata_smoke(database_type, prefix, default_port) -> None:
    required = {
        "host": os.getenv(f"{prefix}_HOST"),
        "database": os.getenv(f"{prefix}_DATABASE"),
        "username": os.getenv(f"{prefix}_USERNAME"),
        "password": os.getenv(f"{prefix}_PASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"{prefix} integration credentials are not configured")

    adapter = adapter_for(database_type)
    resource = adapter.create_runtime_resource(
        **required,
        port=int(os.getenv(f"{prefix}_PORT", str(default_port))),
        timeout_seconds=int(os.getenv(f"{prefix}_TIMEOUT_SECONDS", "15")),
        max_connections=1,
    )
    try:
        with resource.acquire(15) as connection:
            adapter.verify_connection(connection)
            reader = adapter.metadata_reader(connection)
            reader.verify_required_access()
            schemas = reader.discover_schemas()
            requested = tuple(
                value.strip()
                for value in os.getenv(f"{prefix}_SCHEMAS", "").split(",")
                if value.strip()
            )
            if requested:
                tables = reader.load(requested)
                assert all(table.schema in requested for table in tables)
            assert isinstance(schemas, list)
    finally:
        resource.close()
