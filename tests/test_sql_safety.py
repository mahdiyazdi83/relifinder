import pytest

from oracle_relationship_discovery.db.connection import assert_select_only, quote_identifier


def test_select_is_allowed():
    assert_select_only("SELECT OWNER FROM ALL_TABLES WHERE OWNER = :owner")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM T",
        "BEGIN NULL; END;",
        "SELECT * FROM T; DROP TABLE T",
        "ALTER SESSION SET X=1",
    ],
)
def test_non_select_or_multi_statement_is_rejected(sql):
    with pytest.raises(ValueError):
        assert_select_only(sql)


def test_identifier_validation_rejects_injection_and_quoted_names():
    assert quote_identifier("PARTY_ID") == '"PARTY_ID"'
    with pytest.raises(ValueError):
        quote_identifier('PARTY_ID" FROM SECRET --')
