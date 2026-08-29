from oracle_relationship_discovery.analysis.candidate_generator import generate_candidates
from oracle_relationship_discovery.config import DEFAULT_WEIGHTS
from oracle_relationship_discovery.models import ColumnMetadata, TableMetadata


def table(name: str, *columns: ColumnMetadata) -> TableMetadata:
    return TableMetadata("APP", name, columns=list(columns))


def test_generates_party_id_to_party_pk():
    source = ColumnMetadata("APP", "REQUEST", "PARTY_ID", "NUMBER")
    target = ColumnMetadata(
        "APP", "PARTY", "ID", "NUMBER", nullable=False, pk_constraints=("PK_PARTY",)
    )
    result = generate_candidates(
        [table("REQUEST", source), table("PARTY", target)], 40, DEFAULT_WEIGHTS, ()
    )
    assert [(c.source.name, c.target.name) for c in result] == [("PARTY_ID", "ID")]


def test_incompatible_datatype_is_not_generated():
    source = ColumnMetadata("APP", "REQUEST", "PARTY_ID", "DATE")
    target = ColumnMetadata("APP", "PARTY", "ID", "NUMBER", pk_constraints=("PK",))
    assert not generate_candidates(
        [table("REQUEST", source), table("PARTY", target)], 0, DEFAULT_WEIGHTS, ()
    )


def test_composite_pk_component_is_not_a_target():
    source = ColumnMetadata("APP", "CHILD", "ORDER_ID", "NUMBER")
    component = ColumnMetadata(
        "APP",
        "ORDER",
        "ORDER_ID",
        "NUMBER",
        pk_constraints=("PK_ORDER",),
        composite_constraints=("PK_ORDER",),
    )
    candidates = generate_candidates(
        [table("CHILD", source), table("ORDER", component)], 0, DEFAULT_WEIGHTS, ()
    )
    assert all(candidate.target != component for candidate in candidates)


def test_generic_same_named_non_key_candidate_stays_below_threshold():
    source = ColumnMetadata("APP", "EVENT", "STATUS_ID", "NUMBER")
    unrelated = ColumnMetadata("APP", "AUDIT", "STATUS_ID", "NUMBER")
    assert not generate_candidates(
        [table("EVENT", source), table("AUDIT", unrelated)], 40, DEFAULT_WEIGHTS, {"STATUS"}
    )
