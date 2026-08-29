from oracle_relationship_discovery.analysis.name_similarity import (
    compare_names,
    semantic_root,
    tokenize,
)
from oracle_relationship_discovery.models import ColumnMetadata


def col(table: str, name: str) -> ColumnMetadata:
    return ColumnMetadata("APP", table, name, "NUMBER")


def test_normalization_handles_separator_and_compact_forms():
    assert semantic_root("PARTY_ID") == "PARTY"
    assert semantic_root("partyId") == "PARTY"
    assert semantic_root("PARTYID") == "PARTY"
    assert tokenize("REQUEST-NO") == ("REQUEST", "NO")


def test_table_to_id_pattern_is_strong():
    result = compare_names(col("REQUEST", "PARTY_ID"), col("PARTY", "ID"))
    assert result.ratio == 1.0


def test_conventional_table_prefix_does_not_hide_entity_affinity():
    result = compare_names(col("ORDER_LINE", "CUSTOMERID"), col("TB_CUSTOMER", "CUSTOMERID"))
    assert result.ratio == 0.96


def test_compact_column_matches_underscored_prefixed_table():
    result = compare_names(col("CHILD", "SUPERGROUPID"), col("TB_SUPER_GROUP", "SUPERGROUPID"))
    assert result.ratio == 0.96


def test_generic_entity_is_penalized():
    plain = compare_names(col("EVENT", "STATUS_ID"), col("STATUS", "ID"))
    generic = compare_names(col("EVENT", "STATUS_ID"), col("STATUS", "ID"), {"STATUS"})
    assert 0 < generic.ratio < plain.ratio
