from oracle_relationship_discovery.models import ColumnMetadata


def column(schema: str, table: str, name: str, data_type: str = "NUMBER", **kwargs):
    return ColumnMetadata(schema=schema, table=table, name=name, data_type=data_type, **kwargs)
