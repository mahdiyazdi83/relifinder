"""MySQL and MariaDB providers for ReliFinder."""

from oracle_relationship_discovery.providers.mysql.adapter import MySQLAdapter

MYSQL_ADAPTER = MySQLAdapter()
MARIADB_ADAPTER = MySQLAdapter(mariadb=True)

__all__ = ["MARIADB_ADAPTER", "MYSQL_ADAPTER", "MySQLAdapter"]
