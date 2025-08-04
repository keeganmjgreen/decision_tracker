from uuid import UUID

import sqlalchemy as sqla
from sqlalchemy.orm import Session

from expressions import (
    And,
    BooleanExpression,
    Difference,
    EqualToComparison,
    Expression,
    GreaterThanComparison,
    GreaterThanOrEqualToComparison,
    LessThanComparison,
    LessThanOrEqualToComparison,
    Not,
    NotEqualToComparison,
    NumericExpression,
    Or,
    Product,
    Quotient,
    Sum,
)
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


class TestNotExpression:
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


class TestAndExpression:
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

    def test_simplifying_nested_and_expressions(self) -> None:
        assert And(And(a1=True, a2=True), And(b1=True, b2=True)) == And(
            a1=True, a2=True, b1=True, b2=True
        )
        # Not when named:
        assert And(
            a=And(a1=True, a2=True),
            b=And(b1=True, b2=True),
        ) != And(a1=True, a2=True, b1=True, b2=True)


class TestOrExpression:
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

    def test_simplifying_nested_and_expressions(self) -> None:
        assert Or(Or(a1=True, a2=True), Or(b1=True, b2=True)) == Or(
            a1=True, a2=True, b1=True, b2=True
        )
        # Not when named:
        assert Or(
            a=Or(a1=True, a2=True),
            b=Or(b1=True, b2=True),
        ) != Or(a1=True, a2=True, b1=True, b2=True)


class TestConditionalExpression:
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


def test_numeric_expression() -> None:
    assert NumericExpression(a=4).times(b=2.0) == Product(a=4, b=2.0)
    assert NumericExpression(a=4).divided_by(b=2.0) == Quotient(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).plus(b=2.0) == Sum(a=4, b=2.0)
    assert NumericExpression(a=4).minus(b=2.0) == Difference(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).eq(b=2.0) == EqualToComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).neq(b=2.0) == NotEqualToComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).gt(b=2.0) == GreaterThanComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).gte(b=2.0) == GreaterThanOrEqualToComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).lt(b=2.0) == LessThanComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )
    assert NumericExpression(a=4).lte(b=2.0) == LessThanOrEqualToComparison(
        NumericExpression(a=4), NumericExpression(b=2.0)
    )


class TestProductExpression:
    def test_product_expression(self) -> None:
        y = Product(a=4, b=2)
        assert y.value == 8
        assert type(y.value) is int
        assert type(Product(a=4, b=2.0).value) is float
        assert str(y) == "8 because (a := 4) * (b := 2)"
        assert str(y.with_name("y")) == "y := 8 because (a := 4) * (b := 2)"

    def test_simplifying_nested_product_expression(self) -> None:
        assert Product(Product(a1=1, a2=2), Product(b1=3, b2=4)) == Product(
            a1=1, a2=2, b1=3, b2=4
        )
        # Not when named:
        assert Product(
            a=Product(a1=1, a2=2),
            b=Product(b1=3, b2=4),
        ) != Product(a1=1, a2=2, b1=3, b2=4)


def test_quotient_expression() -> None:
    y = Quotient(NumericExpression(a=4), NumericExpression(b=2))
    assert y.value == 2
    assert type(y.value) is float
    assert (
        type(Quotient(NumericExpression(a=4), NumericExpression(b=2.0)).value) is float
    )
    assert str(y) == "2.0 because (a := 4) / (b := 2)"
    assert str(y.with_name("y")) == "y := 2.0 because (a := 4) / (b := 2)"


class TestSumExpression:
    def test_sum_expression(self) -> None:
        y = Sum(a=4, b=2)
        assert y.value == 6
        assert type(y.value) is int
        assert type(Sum(a=4, b=2.0).value) is float
        assert str(y) == "6 because (a := 4) + (b := 2)"
        assert str(y.with_name("y")) == "y := 6 because (a := 4) + (b := 2)"

    def test_simplifying_nested_sum_expressions(self) -> None:
        assert Sum(Sum(a1=True, a2=True), Sum(b1=True, b2=True)) == Sum(
            a1=True, a2=True, b1=True, b2=True
        )
        # Not when named:
        assert Sum(
            a=Sum(a1=True, a2=True),
            b=Sum(b1=True, b2=True),
        ) != Sum(a1=True, a2=True, b1=True, b2=True)


def test_difference_expression() -> None:
    y = Difference(NumericExpression(a=4), NumericExpression(b=2))
    assert y.value == 2
    assert type(y.value) is int
    assert (
        type(Difference(NumericExpression(a=4), NumericExpression(b=2.0)).value)
        is float
    )
    assert str(y) == "2 because (a := 4) - (b := 2)"
    assert str(y.with_name("y")) == "y := 2 because (a := 4) - (b := 2)"


class TestEqualToComparison:
    def test_when_true(self) -> None:
        y = EqualToComparison(NumericExpression(a=4), NumericExpression(b=4.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) == (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) == (b := 4.0)"

    def test_when_false(self) -> None:
        y = EqualToComparison(NumericExpression(a=4), NumericExpression(b=2.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) != (b := 2.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) != (b := 2.0)"


class TestNotEqualToComparison:
    def test_when_true(self) -> None:
        y = NotEqualToComparison(NumericExpression(a=4), NumericExpression(b=2.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) != (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) != (b := 2.0)"

    def test_when_false(self) -> None:
        y = NotEqualToComparison(NumericExpression(a=4), NumericExpression(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) == (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) == (b := 4.0)"


class TestGreaterThanComparison:
    def test_when_true(self) -> None:
        y = GreaterThanComparison(NumericExpression(a=4), NumericExpression(b=2.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) > (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) > (b := 2.0)"

    def test_when_false(self) -> None:
        y = GreaterThanComparison(NumericExpression(a=4), NumericExpression(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) <= (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) <= (b := 4.0)"


class TestGreaterThanOrEqualToComparison:
    def test_when_true(self) -> None:
        # When greater than:
        y = GreaterThanOrEqualToComparison(
            NumericExpression(a=4), NumericExpression(b=2.0)
        )
        assert y.value is True
        assert str(y) == "True because (a := 4) >= (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) >= (b := 2.0)"
        # When equal to:
        y = GreaterThanOrEqualToComparison(
            NumericExpression(a=4), NumericExpression(b=4.0)
        )
        assert y.value is True

    def test_when_false(self) -> None:
        y = GreaterThanOrEqualToComparison(
            NumericExpression(a=2), NumericExpression(b=4.0)
        )
        assert y.value is False
        assert str(y) == "False because (a := 2) < (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 2) < (b := 4.0)"


class TestLessThanComparison:
    def test_when_true(self) -> None:
        y = LessThanComparison(NumericExpression(a=2), NumericExpression(b=4.0))
        assert y.value is True
        assert str(y) == "True because (a := 2) < (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 2) < (b := 4.0)"

    def test_when_false(self) -> None:
        y = LessThanComparison(NumericExpression(a=4), NumericExpression(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) >= (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) >= (b := 4.0)"


class TestLessThanOrEqualToComparison:
    def test_when_true(self) -> None:
        # When less than:
        y = LessThanOrEqualToComparison(
            NumericExpression(a=2), NumericExpression(b=4.0)
        )
        assert y.value is True
        assert str(y) == "True because (a := 2) <= (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 2) <= (b := 4.0)"
        # When equal to:
        y = LessThanOrEqualToComparison(
            NumericExpression(a=4), NumericExpression(b=4.0)
        )
        assert y.value is True

    def test_when_false(self) -> None:
        y = LessThanOrEqualToComparison(
            NumericExpression(a=4), NumericExpression(b=2.0)
        )
        assert y.value is False
        assert str(y) == "False because (a := 4) > (b := 2.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) > (b := 2.0)"


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
