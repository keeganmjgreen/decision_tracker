from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Session

from expressions import And, BooleanExpression, Expression, Not, Or
from schema import EvaluatedExpressionRecord


class TestBooleanExpression:
    def test_boolean_expression(self) -> None:
        y = BooleanExpression(True)
        assert y.value is True
        assert str(y) == "True"
        assert str(BooleanExpression(y=True)) == "y := True"

    def test_and_ing(self) -> None:
        assert BooleanExpression(a=True).and_(b=True, c=True) == And(
            a=True, b=True, c=True
        )
        assert And(a=True, b=True).and_(c=True, d=True) == And(
            a=True, b=True, c=True, d=True
        )

    def test_or_ing(self) -> None:
        assert BooleanExpression(a=True).or_(b=True) == Or(a=True, b=True)
        assert Or(a=True, b=True).or_(c=True) == Or(a=True, b=True, c=True)
        assert BooleanExpression(a=True).or_(b=True, c=True) == Or(
            BooleanExpression(a=True), And(b=True, c=True)
        )


class TestNotOperator:
    def test_when_true(self) -> None:
        y = Not(x=True)
        assert y.value is False
        assert str(y) == "False because x := True"
        assert str(y.with_name("y")) == "y := False because x := True"

    def test_when_false(self) -> None:
        y = Not(x=False)
        assert y.value is True
        assert str(y) == "True because x := False"
        assert str(y.with_name("y")) == "y := True because x := False"


class TestAndOperator:
    def test_when_true(self) -> None:
        y = And(a=True, b=True)
        assert y.value is True
        assert str(y) == "True because (a := True) and (b := True)"
        assert str(y.with_name("y")) == "y := True because (a := True) and (b := True)"

    def test_when_false(self) -> None:
        y = And(a=True, b=False)
        assert y.value is False
        assert str(y) == "False because (b := False)"
        assert str(y.with_name("y")) == "y := False because (b := False)"

    def test_simplifying_nested_and_operators(self) -> None:
        assert And(And(a1=True, a2=True), And(b1=True, b2=True)) == And(
            a1=True, a2=True, b1=True, b2=True
        )
        # Not when named:
        assert And(
            a=And(a1=True, a2=True),
            b=And(b1=True, b2=True),
        ) != And(a1=True, a2=True, b1=True, b2=True)


class TestOrOperator:
    def test_when_true(self) -> None:
        y = Or(a=True, b=False)
        assert y.value is True
        assert str(y) == "True because (a := True)"
        assert str(y.with_name("y")) == "y := True because (a := True)"

    def test_when_false(self) -> None:
        y = Or(a=False, b=False)
        assert y.value is False
        assert str(y) == "False because (a := False) and (b := False)"
        assert (
            str(y.with_name("y")) == "y := False because (a := False) and (b := False)"
        )

    def test_simplifying_nested_and_operators(self) -> None:
        assert Or(Or(a1=True, a2=True), Or(b1=True, b2=True)) == Or(
            a1=True, a2=True, b1=True, b2=True
        )
        # Not when named:
        assert Or(
            a=Or(a1=True, a2=True),
            b=Or(b1=True, b2=True),
        ) != Or(a1=True, a2=True, b1=True, b2=True)


class TestTernaryOperator:
    def test_when_true(self) -> None:
        y = Expression(1).if_(x=True).else_(2)
        assert y.value == 1
        assert str(y) == "1 because x := True"
        assert str(y.with_name("y")) == "y := 1 because x := True"

    def test_when_false(self) -> None:
        y = Expression(1).if_(x=False).else_(2)
        assert y.value == 2
        assert str(y) == "2 because x := False"
        assert str(y.with_name("y")) == "y := 2 because x := False"

    def test_with_named_results(self) -> None:
        """Test when `result_if_true` and/or `result_if_false` are named."""
        y = Expression(a=1).if_(x=True).else_(b=2)
        assert y.value == 1


def test_inserting_expression_into_db(db_engine: sqla.Engine) -> None:
    y = Not(x=True)
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
