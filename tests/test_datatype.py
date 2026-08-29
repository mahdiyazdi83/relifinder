from oracle_relationship_discovery.analysis.datatype import compare_datatypes
from oracle_relationship_discovery.models import ColumnMetadata


def col(kind: str, **kwargs):
    return ColumnMetadata("S", "T", "C", kind, **kwargs)


def test_numeric_precision_differences_are_compatible():
    evidence = compare_datatypes(col("NUMBER", precision=10), col("NUMBER", precision=18))
    assert evidence.compatible and evidence.ratio == 1


def test_date_to_number_is_incompatible():
    assert not compare_datatypes(col("DATE"), col("NUMBER")).compatible


def test_longer_source_text_is_penalized():
    evidence = compare_datatypes(col("VARCHAR2", data_length=100), col("VARCHAR2", data_length=20))
    assert evidence.compatible and evidence.ratio < 1
