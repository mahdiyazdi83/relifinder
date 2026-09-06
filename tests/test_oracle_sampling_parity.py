from contextlib import contextmanager

import pytest

from oracle_relationship_discovery.config import SamplingConfig
from oracle_relationship_discovery.models import (
    ColumnMetadata,
    RelationshipCandidate,
    ScoreBreakdown,
    ValidationStatus,
)
from oracle_relationship_discovery.providers.oracle.sampling import OracleDataSampler


class _Cursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.current_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, binds):
        self.current_sql = sql
        self.executed.append((sql, binds))
        return self

    def fetchall(self):
        if "SELECT sampled_value" in self.current_sql:
            return [(1,), (2,), (2,)]
        if "SELECT DISTINCT" in self.current_sql:
            binds = self.executed[-1][1]
            return [(value,) for value in binds.values()]
        raise AssertionError(self.current_sql)


class _Connection:
    def __init__(self) -> None:
        self.cursor_instance = _Cursor()

    def cursor(self):
        return self.cursor_instance


def _candidate() -> RelationshipCandidate:
    return RelationshipCandidate(
        ColumnMetadata("APP", "CHILD", "PARENT_ID", "NUMBER"),
        ColumnMetadata(
            "APP",
            "PARENT",
            "ID",
            "NUMBER",
            pk_constraints=("PK_PARENT",),
        ),
        ScoreBreakdown(name=35, datatype=15, target_key=15),
    )


@pytest.mark.parametrize(
    ("mode", "expected_clause"),
    [("first", 'FROM "APP"."CHILD"\n'), ("sample", "SAMPLE BLOCK (1)")],
)
def test_oracle_sampling_keeps_bounds_binds_and_no_raw_evidence(mode, expected_clause) -> None:
    connection = _Connection()

    @contextmanager
    def acquire():
        yield connection

    candidate = _candidate()
    OracleDataSampler(
        acquire,
        SamplingConfig(
            max_source_rows=3,
            bind_batch_size=1,
            mode=mode,
        ),
    ).validate(candidate)

    executed = connection.cursor_instance.executed
    assert "ROWNUM <= :row_limit" in executed[0][0]
    assert expected_clause in executed[0][0]
    assert executed[0][1] == {"row_limit": 3}
    assert len([sql for sql, _binds in executed if "SELECT DISTINCT" in sql]) == 2
    assert candidate.evidence.status == ValidationStatus.VALIDATED
    assert candidate.evidence.match_ratio == 1
    assert not hasattr(candidate.evidence, "sampled_values")
