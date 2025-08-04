from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, ClassVar, Self, cast
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from schema import EvaluatedExpressionRecord
from utils import get_exactly_one

# ======================================================================================
# Generic Expression


class Expression[T]:
    value: T
    _id: UUID
    _name: str | None
    _operator: ClassVar[str | None] = None
    _operands: list[Expression[T]]

    def __init__(self, *unnamed_values: T, **named_values: T) -> None:
        if len(unnamed_values) > 0:
            if len(named_values) > 0:
                raise ValueError(
                    "Either `unnamed_values` or `named_values` must contain a value, "
                    "not both."
                )
            self.value = get_exactly_one(unnamed_values)
            self._name = None
        else:
            self.value = get_exactly_one(named_values.values())
            self._name = get_exactly_one(named_values.keys())
        self._id = uuid4()
        self._operands = []

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Expression):
            return (
                self._name == other._name
                and self._operator == other._operator
                and self._operands == other._operands
            )
        else:
            return False

    def with_name(self, name: str) -> Self:
        self = deepcopy(self)
        self._name = name
        return self

    def if_(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> IncompleteConditional:
        condition = _handle_boolean_expressions(
            unnamed_expressions, named_expressions, multiple_output=False
        )
        return IncompleteConditional(
            result_if_true=(self.value if type(self) is Expression else self),
            condition=cast(BooleanExpression, condition),
        )

    @property
    def evaluated_expression(self) -> Expression[Any]:
        return self

    @property
    def reason(self) -> str:
        return (f"{self._name} := " if self._name else "") + f"{self.value}"

    def __str__(self) -> str:
        return self.reason

    @property
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        return EvaluatedExpressionRecord(
            id=self._id,  # type: ignore
            name=self._name,
            value=self.value,
            operator=self._operator,
            children=[o.evaluated_expression_record for o in self._operands],
        )

    def to_db(self, db_engine: Engine) -> None:
        with Session(db_engine) as session:
            session.add(self.evaluated_expression_record)  # Also adds children.
            session.commit()


# ======================================================================================
# Boolean Expression


class BooleanExpression(Expression[bool]):
    _operands: list[BooleanExpression]

    def and_(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> And:
        return And(
            self,
            *cast(
                list[BooleanExpression],
                _handle_boolean_expressions(
                    unnamed_expressions, named_expressions, multiple_output=True
                ),
            ),
        )

    def or_(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> Or:
        return Or(
            self,
            cast(
                BooleanExpression,
                _handle_boolean_expressions(
                    unnamed_expressions, named_expressions, multiple_output=False
                ),
            ),
        )

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return self


class Not(BooleanExpression):
    _operator: ClassVar[str | None] = "not"
    _operand: BooleanExpression

    def __init__(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operand = cast(
            BooleanExpression,
            _handle_boolean_expressions(
                unnamed_expressions, named_expressions, multiple_output=False
            ),
        )

    @property
    def _operands(self) -> list[BooleanExpression]:
        return [self._operand]

    @property
    def value(self) -> bool:
        return not self._operand.value

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return (
            Not(self._operand.evaluated_expression)
            if self.value
            else self._operand.evaluated_expression
        )

    @property
    def reason(self) -> str:
        return self._operand.reason

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class And(BooleanExpression):
    _operator: ClassVar[str | None] = "and"
    _operands: list[BooleanExpression]

    def __init__(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in cast(
            list[BooleanExpression],
            _handle_boolean_expressions(unnamed_expressions, named_expressions),
        ):
            if o._name is not None or not isinstance(o, And):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def value(self) -> bool:
        return all(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return (
            And(*[o.evaluated_expression for o in self._operands])
            if self.value
            else Or(
                *[Not(o) for o in self._operands if not o.value]
            ).evaluated_expression
        )

    @property
    def reason(self) -> str:
        return (
            " and ".join(f"({o.reason})" for o in self._operands)
            if self.value
            else self.evaluated_expression.reason
        )

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class Or(BooleanExpression):
    _operator: ClassVar[str | None] = "or"
    _operands: list[BooleanExpression]

    def __init__(
        self,
        *unnamed_expressions: BooleanExpression,
        **named_expressions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in cast(
            list[BooleanExpression],
            _handle_boolean_expressions(unnamed_expressions, named_expressions),
        ):
            if o._name is not None or not isinstance(o, Or):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def value(self) -> bool:
        return any(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return (
            Or(*[o.evaluated_expression for o in self._operands if o.value])
            if self.value
            else And(*[Not(o) for o in self._operands]).evaluated_expression
        )

    @property
    def reason(self) -> str:
        return (
            " or ".join(f"({o.reason})" for o in self._operands if o.value)
            if self.value
            else self.evaluated_expression.reason
        )

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


def _handle_boolean_expressions(
    unnamed_expressions: tuple[BooleanExpression, ...],
    named_expressions: dict[str, BooleanExpression | bool],
    allow_multiple_input: bool = True,
    multiple_output: bool = True,
) -> BooleanExpression | list[BooleanExpression]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, BooleanExpression) else BooleanExpression(e)).with_name(n)
        for n, e in named_expressions.items()
    ]
    if len(expressions) == 0:
        raise Exception
    elif len(expressions) > 1 and not allow_multiple_input:
        raise Exception
    if not multiple_output:
        if len(expressions) > 1:
            return And(*expressions)
        else:
            return get_exactly_one(expressions)
    else:
        return expressions


# ======================================================================================
# Conditional Expression


class IncompleteConditional:
    _result_if_true: Expression[Any] | Any
    _condition: BooleanExpression

    def __init__(
        self, result_if_true: Expression[Any] | Any, condition: BooleanExpression
    ) -> None:
        self._result_if_true = result_if_true
        self._condition = condition

    def else_(
        self,
        *unnamed_values: Any,
        **named_values: Expression[Any] | Any,
    ) -> Conditional:
        return Conditional(
            self._result_if_true,
            self._condition,
            result_if_false=Expression(*unnamed_values, **named_values),
        )


class Conditional(Expression[Any]):
    _result_if_true: Expression[Any] | Any
    _condition: BooleanExpression
    _result_if_false: Expression[Any] | Any

    def __init__(
        self,
        result_if_true: Expression[Any] | Any,
        condition: BooleanExpression,
        result_if_false: Expression[Any] | Any,
    ) -> None:
        self._name = None
        self._result_if_true = result_if_true
        self._condition = condition
        self._result_if_false = result_if_false

    @property
    def value(self) -> bool:
        return (
            self._value_of(self._result_if_true)
            if self._value_of(self._condition)
            else self._value_of(self._result_if_false)
        )

    @staticmethod
    def _value_of[T](x: Expression[T] | T) -> T:
        if isinstance(x, Expression):
            return x.value
        else:
            return x

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return self._condition.evaluated_expression

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.evaluated_expression.reason
        )


# ======================================================================================
# Numeric Expression


N = int | float


class NumericExpression(Expression[N]):
    _operands: list[NumericExpression]

    def times(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> Product:
        return Product(
            self, *_numeric_expressions_from(unnamed_expressions, named_expressions)
        )

    def divided_by(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> Quotient:
        return Quotient(
            dividend=self,
            divisor=_one_numeric_expression_from(
                unnamed_expressions, named_expressions
            ),
        )

    def plus(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> Sum:
        return Sum(
            self, *_numeric_expressions_from(unnamed_expressions, named_expressions)
        )

    def minus(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> Difference:
        return Difference(
            minuend=self,
            subtrahend=_one_numeric_expression_from(
                unnamed_expressions, named_expressions
            ),
        )

    def eq(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> EqualToComparison:
        return EqualToComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    def neq(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> NotEqualToComparison:
        return NotEqualToComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    def gt(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> GreaterThanComparison:
        return GreaterThanComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    def gte(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> GreaterThanOrEqualToComparison:
        return GreaterThanOrEqualToComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    def lt(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> LessThanComparison:
        return LessThanComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    def lte(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> LessThanOrEqualToComparison:
        return LessThanOrEqualToComparison(
            lhs=self,
            rhs=_one_numeric_expression_from(unnamed_expressions, named_expressions),
        )

    @property
    def evaluated_expression(self) -> NumericExpression:
        return self


class Product(NumericExpression):
    _operator: ClassVar[str | None] = "times"
    _operands: list[NumericExpression]

    def __init__(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in _numeric_expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, Product):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def value(self) -> N:
        return math.prod(o.value for o in self._operands)

    @property
    def reason(self) -> str:
        return " * ".join(f"({o.reason})" for o in self._operands)

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class Quotient(NumericExpression):
    _operator: ClassVar[str | None] = "divided by"
    _dividend: NumericExpression
    _divisor: NumericExpression

    def __init__(self, dividend: NumericExpression, divisor: NumericExpression) -> None:
        self._id = uuid4()
        self._name = None
        self._dividend = dividend
        self._divisor = divisor

    @property
    def _operands(self) -> list[NumericExpression]:
        return [self._dividend, self._divisor]  # Order matters.

    @property
    def value(self) -> float:
        return self._dividend.value / self._divisor.value

    @property
    def reason(self) -> str:
        return f"({self._dividend.reason}) / ({self._divisor.reason})"

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class Sum(NumericExpression):
    _operator: ClassVar[str | None] = "plus"
    _operands: list[NumericExpression]

    def __init__(
        self,
        *unnamed_expressions: NumericExpression,
        **named_expressions: NumericExpression | N,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in _numeric_expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, Sum):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def value(self) -> N:
        return sum(o.value for o in self._operands)

    @property
    def reason(self) -> str:
        return " + ".join(f"({o.reason})" for o in self._operands if o.value)

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class Difference(NumericExpression):
    _operator: ClassVar[str | None] = "divided by"
    _minuend: NumericExpression
    _subtrahend: NumericExpression

    def __init__(
        self, minuend: NumericExpression, subtrahend: NumericExpression
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._minuend = minuend
        self._subtrahend = subtrahend

    @property
    def _operands(self) -> list[NumericExpression]:
        return [self._minuend, self._subtrahend]  # Order matters.

    @property
    def value(self) -> N:
        return self._minuend.value - self._subtrahend.value

    @property
    def reason(self) -> str:
        return f"({self._minuend.reason}) - ({self._subtrahend.reason})"

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class _NumericComparison(BooleanExpression):
    _operator: ClassVar[str | None]
    _lhs: NumericExpression
    _rhs: NumericExpression

    def __init__(self, lhs: NumericExpression, rhs: NumericExpression) -> None:
        self._id = uuid4()
        self._name = None
        self._lhs = lhs
        self._rhs = rhs

    @property
    def _operands(self) -> list[NumericExpression]:
        return [self._lhs, self._rhs]  # Order may matter.

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )


class EqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is equal to"

    @property
    def value(self) -> bool:
        return self._lhs.value == self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else NotEqualToComparison(self._lhs, self._rhs)

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) == ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


class NotEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is not equal to"

    @property
    def value(self) -> bool:
        return self._lhs.value != self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else EqualToComparison(self._lhs, self._rhs)

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) != ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


class GreaterThanComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is greater than"

    @property
    def value(self) -> bool:
        return self._lhs.value > self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else LessThanOrEqualToComparison(self._lhs, self._rhs)

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) > ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


class GreaterThanOrEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is greater than or equal to"

    @property
    def value(self) -> bool:
        return self._lhs.value >= self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else LessThanComparison(self._lhs, self._rhs)

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) >= ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


class LessThanComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is less than"

    @property
    def value(self) -> bool:
        return self._lhs.value < self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return (
            self if self.value else GreaterThanOrEqualToComparison(self._lhs, self._rhs)
        )

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) < ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


class LessThanOrEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is less than or equal to"

    @property
    def value(self) -> bool:
        return self._lhs.value <= self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else GreaterThanComparison(self._lhs, self._rhs)

    @property
    def reason(self) -> str:
        return (
            f"({self._lhs.reason}) <= ({self._rhs.reason})"
            if self.value
            else self.evaluated_expression.reason
        )


def _one_numeric_expression_from(
    unnamed_expressions: tuple[NumericExpression, ...],
    named_expressions: dict[str, NumericExpression | N],
) -> NumericExpression:
    return get_exactly_one(
        _numeric_expressions_from(unnamed_expressions, named_expressions)
    )


def _numeric_expressions_from(
    unnamed_expressions: tuple[NumericExpression, ...],
    named_expressions: dict[str, NumericExpression | N],
) -> list[NumericExpression]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, NumericExpression) else NumericExpression(e)).with_name(n)
        for n, e in named_expressions.items()
    ]
    if len(expressions) == 0:
        raise Exception
    return expressions
