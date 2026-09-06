"""Oracle provider for ReliFinder's database-neutral discovery core."""

from oracle_relationship_discovery.providers.oracle.adapter import OracleAdapter

ORACLE_ADAPTER = OracleAdapter()

__all__ = ["ORACLE_ADAPTER", "OracleAdapter"]
