from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Session

from expressions import And, Expression, Not
from schema import EvaluatedExpressionRecord


def test_not_expression(db_engine: sqla.Engine) -> None:
    # Test when condition is True:
    y = Not(x=True)
    assert y.value is False
    assert str(y) == "False because x := True"
    assert str(y.with_name("y")) == "y := False because x := True"
    y.to_db(db_engine)
    with Session(db_engine) as session:
        records = session.scalars(sqla.select(EvaluatedExpressionRecord)).all()
        record_1, record_2 = records
        assert isinstance(record_1.id, UUID)
        assert record_1.parent_id is None
        assert record_1.name is None
        assert record_1.value is False
        assert record_1.operator == "not"
        assert record_2.parent_id == record_1.id
        assert record_2.name == "x"
        assert record_2.value is True
        assert record_2.operator is None

    # Test when condition is False:
    y = Not(x=False)
    assert y.value is True
    assert str(y) == "True because x := False"
    assert str(y.with_name("y")) == "y := True because x := False"


def test_and_expression() -> None:
    y = And(a=True, b=True)
    assert y.value is True
    assert str(y) == "True because (a := True) and (b := True)"
    assert str(y.with_name("y")) == "y := True because (a := True) and (b := True)"

    y = And(a=True, b=False)
    assert y.value is False
    assert str(y) == "False because (b := False)"
    assert str(y.with_name("y")) == "y := False because (b := False)"


def test_if_else() -> None:
    # Test when condition is True:
    y = Expression(1).if_(x=True).else_(2)
    assert y.value == 1
    assert str(y) == "1 because x := True"
    assert str(y.with_name("y")) == "y := 1 because x := True"

    # Test when condition is False:
    y = Expression(1).if_(x=False).else_(2)
    assert y.value == 2
    assert str(y) == "2 because x := False"
    assert str(y.with_name("y")) == "y := 2 because x := False"

    # Test when result_if_true and/or result_if_false are named:
    y = Expression(a=1).if_(x=True).else_(b=2)
    assert y.value == 1
