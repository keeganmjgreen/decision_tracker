from uuid import UUID

import pytest
import sqlalchemy as sqla
from sqlalchemy.orm import Session

from expressions import (
    And,
    BaseLiteralExpression,
    EqualToComparison,
    GreaterThanComparison,
    GreaterThanOrEqualToComparison,
    Inverse,
    LessThanComparison,
    LessThanOrEqualToComparison,
    Negative,
    Not,
    NotEqualToComparison,
    Or,
    Product,
    Sum,
    UncertainLookup,
)
from expressions import (
    BooleanLiteralExpression as BooleanLiteral,
)
from expressions import (
    NumericLiteralExpression as NumericLiteral,
)
from schema import EvaluatedExpressionRecord


class TestBooleanExpression:
    def test_boolean_expression(self) -> None:
        y = BooleanLiteral(True)
        assert y.value is True
        assert str(y) == "True"
        assert str(BooleanLiteral(y=True)) == "y := True"

    def test_and_ing(self) -> None:
        assert BooleanLiteral(a=True).and_(b=True, c=True) == And(
            a=True, b=True, c=True
        )
        assert And(a=True, b=True).and_(c=True, d=True) == And(
            a=True, b=True, c=True, d=True
        )

    def test_or_ing(self) -> None:
        assert BooleanLiteral(a=True).or_(b=True) == Or(a=True, b=True)
        assert Or(a=True, b=True).or_(c=True) == Or(a=True, b=True, c=True)
        assert BooleanLiteral(a=True).or_(b=True, c=True) == Or(
            BooleanLiteral(a=True), And(b=True, c=True)
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
        y = NumericLiteral(1).if_(x=True).else_(2)
        assert y.value == 1
        assert str(y) == "1 because x := True"
        assert str(y.with_name("y")) == "y := 1 because x := True"

    def test_when_false(self) -> None:
        y = NumericLiteral(1).if_(x=False).else_(2)
        assert y.value == 2
        assert str(y) == "2 because x := False"
        assert str(y.with_name("y")) == "y := 2 because x := False"

    def test_with_named_results(self) -> None:
        """Test when `result_if_true` and/or `result_if_false` are named."""
        y = NumericLiteral(a=1).if_(x=True).else_(b=2)
        assert y.value == 1


class TestUncertainLookup:
    def test_with_literal_values(self) -> None:
        lookup = UncertainLookup({1: "1", 2: "2"}, 2, "3")
        assert lookup.value == "2"
        # Key not found:
        lookup = UncertainLookup({1: "1", 2: "2"}, 3, "3")
        assert lookup.value == "3"

    def test_with_expression_values(self) -> None:
        lookup = UncertainLookup(
            {1: BaseLiteralExpression("1"), 2: BaseLiteralExpression("2")},
            2,
            BaseLiteralExpression("3"),
        )
        assert lookup.value == "2"
        # Key not found:
        lookup = UncertainLookup(
            {1: BaseLiteralExpression("1"), 2: BaseLiteralExpression("2")},
            3,
            BaseLiteralExpression("3"),
        )
        assert lookup.value == "3"


def test_numeric_expression() -> None:
    assert NumericLiteral(a=4).times(b=2.0) == Product(a=4, b=2.0)
    assert NumericLiteral(a=4).divided_by(b=2.0) == Product(
        NumericLiteral(a=4), Inverse(b=2.0)
    )
    assert NumericLiteral(a=4).plus(b=2.0) == Sum(a=4, b=2.0)
    assert NumericLiteral(a=4).minus(b=2.0) == Sum(NumericLiteral(a=4), Negative(b=2.0))
    assert NumericLiteral(a=4).eq(b=2.0) == EqualToComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
    )
    assert NumericLiteral(a=4).neq(b=2.0) == NotEqualToComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
    )
    assert NumericLiteral(a=4).gt(b=2.0) == GreaterThanComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
    )
    assert NumericLiteral(a=4).gte(b=2.0) == GreaterThanOrEqualToComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
    )
    assert NumericLiteral(a=4).lt(b=2.0) == LessThanComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
    )
    assert NumericLiteral(a=4).lte(b=2.0) == LessThanOrEqualToComparison(
        NumericLiteral(a=4), NumericLiteral(b=2.0)
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

    def test_with_an_inverse_expression_in_the_beginning(self) -> None:
        assert (
            str(Product(a=Inverse(a1=4), b=2)) == "0.5 because 1 / (a1 := 4) * (b := 2)"
        )

    def test_with_an_inverse_expression_in_the_middle_or_end(self) -> None:
        assert str(Product(a=4, b=Inverse(b1=2))) == "2.0 because (a := 4) / (b1 := 2)"

    def test_with_a_negative_expression_in_the_beginning(self) -> None:
        assert str(Product(a=Negative(a1=4), b=2)) == "-8 because -(a1 := 4) * (b := 2)"

    def test_with_a_negative_expression_in_the_middle_or_end(self) -> None:
        assert str(Product(a=4, b=Negative(b1=2))) == "-8 because (a := 4) * -(b1 := 2)"


def test_inverse_expression() -> None:
    y = Inverse(NumericLiteral(a=4))
    assert y.value == 0.25
    assert type(y.value) is float
    assert type(Inverse(NumericLiteral(a=4.0)).value) is float
    assert str(y) == "0.25 because 1 / (a := 4)"
    assert str(y.with_name("y")) == "y := 0.25 because 1 / (a := 4)"


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

    def test_with_a_negative_expression_in_the_beginning(self) -> None:
        assert str(Sum(a=Negative(a1=4), b=2)) == "-2 because -(a1 := 4) + (b := 2)"

    def test_with_a_negative_expression_in_the_middle_or_end(self) -> None:
        assert str(Sum(a=4, b=Negative(b1=2))) == "2 because (a := 4) - (b1 := 2)"

    def test_with_an_inverse_expression_in_the_beginning(self) -> None:
        assert str(Sum(a=Inverse(a1=4), b=2)) == "2.25 because 1 / (a1 := 4) + (b := 2)"

    def test_with_an_inverse_expression_in_the_middle_or_end(self) -> None:
        assert str(Sum(a=4, b=Inverse(b1=2))) == "4.5 because (a := 4) + 1 / (b1 := 2)"


def test_negative_expression() -> None:
    y = Negative(NumericLiteral(a=4))
    assert y.value == -4
    assert type(y.value) is int
    assert type(Negative(NumericLiteral(a=4.0)).value) is float
    assert str(y) == "-4 because -(a := 4)"
    assert str(y.with_name("y")) == "y := -4 because -(a := 4)"


def test_negative_of_inverse() -> None:
    assert str(Negative(a=Inverse(a1=4))) == "-0.25 because -(1 / (a1 := 4))"


class TestEqualToComparison:
    def test_when_true(self) -> None:
        y = EqualToComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) == (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) == (b := 4.0)"

    def test_when_false(self) -> None:
        y = EqualToComparison(NumericLiteral(a=4), NumericLiteral(b=2.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) != (b := 2.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) != (b := 2.0)"


class TestNotEqualToComparison:
    def test_when_true(self) -> None:
        y = NotEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=2.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) != (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) != (b := 2.0)"

    def test_when_false(self) -> None:
        y = NotEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) == (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) == (b := 4.0)"


class TestGreaterThanComparison:
    def test_when_true(self) -> None:
        y = GreaterThanComparison(NumericLiteral(a=4), NumericLiteral(b=2.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) > (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) > (b := 2.0)"

    def test_when_false(self) -> None:
        y = GreaterThanComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) <= (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) <= (b := 4.0)"


class TestGreaterThanOrEqualToComparison:
    def test_when_true(self) -> None:
        # When greater than:
        y = GreaterThanOrEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=2.0))
        assert y.value is True
        assert str(y) == "True because (a := 4) >= (b := 2.0)"
        assert str(y.with_name("y")) == "y := True because (a := 4) >= (b := 2.0)"
        # When equal to:
        y = GreaterThanOrEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is True

    def test_when_false(self) -> None:
        y = GreaterThanOrEqualToComparison(NumericLiteral(a=2), NumericLiteral(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 2) < (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 2) < (b := 4.0)"


class TestLessThanComparison:
    def test_when_true(self) -> None:
        y = LessThanComparison(NumericLiteral(a=2), NumericLiteral(b=4.0))
        assert y.value is True
        assert str(y) == "True because (a := 2) < (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 2) < (b := 4.0)"

    def test_when_false(self) -> None:
        y = LessThanComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) >= (b := 4.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) >= (b := 4.0)"


class TestLessThanOrEqualToComparison:
    def test_when_true(self) -> None:
        # When less than:
        y = LessThanOrEqualToComparison(NumericLiteral(a=2), NumericLiteral(b=4.0))
        assert y.value is True
        assert str(y) == "True because (a := 2) <= (b := 4.0)"
        assert str(y.with_name("y")) == "y := True because (a := 2) <= (b := 4.0)"
        # When equal to:
        y = LessThanOrEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=4.0))
        assert y.value is True

    def test_when_false(self) -> None:
        y = LessThanOrEqualToComparison(NumericLiteral(a=4), NumericLiteral(b=2.0))
        assert y.value is False
        assert str(y) == "False because (a := 4) > (b := 2.0)"
        assert str(y.with_name("y")) == "y := False because (a := 4) > (b := 2.0)"


class TestToDb:
    def test_inserting_expression_into_db(self, db_engine: sqla.Engine) -> None:
        y = Not(x=True).with_name("y")
        y.to_db(db_engine)
        with Session(db_engine) as session:
            records = session.scalars(sqla.select(EvaluatedExpressionRecord)).all()
            record_1, record_2 = records
            assert isinstance(record_1.id, UUID)
            assert record_1.parent_id is None
            assert record_1.name == "y"
            assert record_1.value is False
            assert record_1.operator == "not"
            assert record_2.parent_id == record_1.id
            assert record_2.name == "x"
            assert record_2.value is True
            assert record_2.operator is None

    def test_raising_if_root_expression_is_unnamed(
        self, db_engine: sqla.Engine
    ) -> None:
        x = Not(x=True)
        with pytest.raises(ValueError):
            x.to_db(db_engine)
