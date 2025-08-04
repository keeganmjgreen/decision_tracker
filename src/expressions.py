from __future__ import annotations

import abc
import math
from copy import deepcopy
from typing import Any, ClassVar, Self, cast, override
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from schema import EvaluatedExpressionRecord
from utils import get_exactly_one

# ======================================================================================
# Base expressions


class BaseExpression[T](abc.ABC):
    _id: UUID
    _name: str | None
    _operator: ClassVar[str | None]
    _short_operator: ClassVar[str | None]

    def __init__(self) -> None:
        self._id = uuid4()
        self._name = None

    @property
    @abc.abstractmethod
    def operands(self) -> list[BaseExpression[Any]]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def value(self) -> T:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def evaluated_expression(self) -> BaseExpression[T]:
        raise NotImplementedError

    @property
    def reason(self) -> str:
        return f" {self._short_operator} ".join(f"({o.reason})" for o in self.operands)

    def __str__(self) -> str:
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.reason
        )

    @property
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        return EvaluatedExpressionRecord(
            id=self._id,  # type: ignore
            name=self._name,
            value=self.value,
            operator=self._operator,
            children=[o.evaluated_expression_record for o in self.operands],
        )

    def to_db(self, db_engine: Engine) -> None:
        with Session(db_engine) as session:
            session.add(self.evaluated_expression_record)  # Also adds children.
            session.commit()

    def with_name(self, name: str) -> Self:
        self = deepcopy(self)
        self._name = name
        return self

    def if_(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> IncompleteConditional[T]:
        condition = _one_boolean_expression_from(unnamed_expressions, named_expressions)
        return IncompleteConditional(
            result_if_true=_value_of(self),
            condition=condition,
        )

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BaseExpression):
            other = cast(BaseExpression[T], other)
            return (
                self._name == other._name
                and self._operator == other._operator
                and self.operands == other.operands
                and self.value == other.value
            )
        else:
            return False


class BaseLiteralExpression[T](BaseExpression[T]):
    _literal_value: T
    _operator: ClassVar[str | None] = None
    _short_operator: ClassVar[str | None] = _operator

    def __init__(self, *unnamed_values: T, **named_values: T) -> None:
        super().__init__()
        if len(unnamed_values) > 0:
            if len(named_values) > 0:
                raise ValueError(
                    "Either `unnamed_values` or `named_values` must contain a value, "
                    "not both."
                )
            self._literal_value = get_exactly_one(unnamed_values)
        else:
            self._literal_value = get_exactly_one(named_values.values())
            self._name = get_exactly_one(named_values.keys())

    @property
    def value(self) -> T:
        return self._literal_value

    @property
    def operands(self) -> list[BaseExpression[T]]:
        return []

    @property
    def evaluated_expression(self) -> BaseExpression[T]:
        return self

    @property
    @override
    def reason(self) -> str:
        return (f"{self._name} := " if self._name else "") + f"{self.value}"

    @override
    def __str__(self) -> str:
        return self.reason


def _one_expression_from[T](
    unnamed_expressions: tuple[BaseExpression[T], ...],
    named_expressions: dict[str, BaseExpression[T] | T],
) -> BaseExpression[T]:
    return get_exactly_one(_expressions_from(unnamed_expressions, named_expressions))


def _expressions_from[T](
    unnamed_expressions: tuple[BaseExpression[T], ...],
    named_expressions: dict[str, BaseExpression[T] | T],
) -> list[BaseExpression[T]]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, BaseExpression) else BaseLiteralExpression[T](e)).with_name(
            n
        )
        for n, e in named_expressions.items()
    ]
    if len(expressions) == 0:
        raise Exception
    return expressions


def _value_of[T](x: BaseExpression[T] | T) -> T:
    if isinstance(x, BaseExpression):
        x = cast(BaseExpression[T], x)
        return x.value
    else:
        return x


# ======================================================================================
# Boolean expressions


class BooleanBaseExpression(BaseExpression[bool]):
    @property
    @override
    def reason(self) -> str:
        return (
            f" {self._short_operator} ".join(f"({o.reason})" for o in self.operands)
            if self.value
            else self.evaluated_expression.reason
        )

    def and_(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> And:
        return And(self, *_expressions_from(unnamed_expressions, named_expressions))

    def or_(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> Or:
        return Or(
            self, _one_boolean_expression_from(unnamed_expressions, named_expressions)
        )


class BooleanLiteralExpression(BaseLiteralExpression[bool], BooleanBaseExpression):
    pass


class Not(BooleanBaseExpression):
    _operator: ClassVar[str | None] = "not"
    _short_operator: ClassVar[str | None] = _operator
    _operand: BaseExpression[bool]

    def __init__(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> None:
        super().__init__()
        self._operand = _one_boolean_expression_from(
            unnamed_expressions, named_expressions
        )

    @property
    def operands(self) -> list[BaseExpression[bool]]:
        return [self._operand]

    @property
    def value(self) -> bool:
        return not self._operand.value

    @property
    def evaluated_expression(self) -> BaseExpression[bool]:
        return (
            Not(self._operand.evaluated_expression)
            if self.value
            else self._operand.evaluated_expression
        )

    @property
    def reason(self) -> str:
        return self._operand.reason


class And(BooleanBaseExpression):
    _operator: ClassVar[str | None] = "and"
    _short_operator: ClassVar[str | None] = _operator
    _operands: list[BaseExpression[bool]]

    def __init__(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> None:
        super().__init__()
        self._operands = []
        for o in _expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, And):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def operands(self) -> list[BaseExpression[bool]]:
        return self._operands

    @property
    def value(self) -> bool:
        return all(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> BaseExpression[bool]:
        return (
            And(*[o.evaluated_expression for o in self._operands])
            if self.value
            else Or(
                *[Not(o) for o in self._operands if not o.value]
            ).evaluated_expression
        )


class Or(BooleanBaseExpression):
    _operator: ClassVar[str | None] = "or"
    _short_operator: ClassVar[str | None] = _operator
    _operands: list[BaseExpression[bool]]

    def __init__(
        self,
        *unnamed_expressions: BaseExpression[bool],
        **named_expressions: BaseExpression[bool] | bool,
    ) -> None:
        super().__init__()
        self._operands = []
        for o in _expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, Or):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def operands(self) -> list[BaseExpression[bool]]:
        return self._operands

    @property
    def value(self) -> bool:
        return any(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> BaseExpression[bool]:
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


def _one_boolean_expression_from(
    unnamed_expressions: tuple[BaseExpression[bool], ...],
    named_expressions: dict[str, BaseExpression[bool] | bool],
    allow_multiple_input: bool = True,
) -> BaseExpression[bool]:
    expressions = _expressions_from(unnamed_expressions, named_expressions)
    if len(expressions) > 1 and not allow_multiple_input:
        raise Exception
    if len(expressions) > 1:
        return And(*expressions)
    else:
        return get_exactly_one(expressions)


# ======================================================================================
# Conditional expressions


class IncompleteConditional[RT]:
    _result_if_true: BaseExpression[RT] | RT
    _condition: BaseExpression[bool]

    def __init__(
        self, result_if_true: BaseExpression[RT] | RT, condition: BaseExpression[bool]
    ) -> None:
        self._result_if_true = result_if_true
        self._condition = condition

    def else_(
        self,
        *unnamed_values: BaseExpression[RT] | RT,
        **named_values: BaseExpression[RT] | RT,
    ) -> Conditional[RT]:
        unnamed_value_list: list[BaseExpression[RT]] = [
            (
                unnamed_value
                if isinstance(unnamed_value, BaseExpression)
                else BaseLiteralExpression[RT](unnamed_value)
            )
            for unnamed_value in unnamed_values
        ]
        return Conditional(
            self._result_if_true,
            self._condition,
            result_if_false=_one_expression_from(
                tuple(unnamed_value_list), named_values
            ),
        )


class Conditional[RT](BaseExpression[RT]):
    _result_if_true: BaseExpression[RT] | RT
    _condition: BaseExpression[bool]
    _result_if_false: BaseExpression[RT] | RT

    def __init__(
        self,
        result_if_true: BaseExpression[RT] | RT,
        condition: BaseExpression[bool] | bool,
        result_if_false: BaseExpression[RT] | RT,
    ) -> None:
        super().__init__()
        self._result_if_true = result_if_true
        self._condition = (
            condition
            if isinstance(condition, BaseExpression)
            else BaseLiteralExpression[bool](condition)
        )
        self._result_if_false = result_if_false

    @property
    def operands(self) -> list[BaseExpression[bool]]:
        return self.evaluated_expression.operands

    @property
    def value(self) -> RT:
        return (
            _value_of(self._result_if_true)
            if _value_of(self._condition)
            else _value_of(self._result_if_false)
        )

    @property
    def evaluated_expression(self) -> BaseExpression[bool]:
        return self._condition.evaluated_expression

    @property
    @override
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        raise Exception

    @property
    def reason(self) -> str:
        return self.evaluated_expression.reason

    @override
    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.evaluated_expression.reason
        )


class Lookup[K, V](BaseExpression[V]):
    _lookup_dict: dict[K, BaseExpression[V]]
    _default: BaseExpression[V]
    _look_up_key: BaseExpression[K]

    def __init__(
        self,
        lookup_dict: dict[K, BaseExpression[V] | V],
        look_up_key: BaseExpression[K] | K,
        default: BaseExpression[V] | V,
    ) -> None:
        super().__init__()
        self._lookup_dict = {
            k: (v if isinstance(v, BaseExpression) else BaseLiteralExpression[V](v))
            for k, v in lookup_dict.items()
        }
        self._look_up_key = (
            look_up_key
            if isinstance(look_up_key, BaseExpression)
            else BaseLiteralExpression[K](look_up_key)
        )
        self._default = (
            default
            if isinstance(default, BaseExpression)
            else BaseLiteralExpression[V](default)
        )

    @property
    def operands(self) -> list[BaseExpression[bool]]:
        return self.evaluated_expression.operands

    @property
    def value(self) -> V:
        return (
            {k: v for k, v in self._lookup_dict.items()}
            .get(self._look_up_key.value, self._default)
            .value
        )

    @property
    def evaluated_expression(self) -> BaseExpression[K]:
        return self._look_up_key.evaluated_expression

    @property
    @override
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        raise Exception

    @property
    def reason(self) -> str:
        return self.evaluated_expression.reason

    @override
    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.evaluated_expression.reason
        )


# ======================================================================================
# Numeric expressions


N = int | float


class NumericBaseExpression(BaseExpression[N]):
    def times(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> Product:
        return Product(self, *_expressions_from(unnamed_expressions, named_expressions))

    def divided_by(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> Quotient:
        return Quotient(
            dividend=self,
            divisor=_one_expression_from(unnamed_expressions, named_expressions),
        )

    def plus(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> Sum:
        return Sum(self, *_expressions_from(unnamed_expressions, named_expressions))

    def minus(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> Difference:
        return Difference(
            minuend=self,
            subtrahend=_one_expression_from(unnamed_expressions, named_expressions),
        )

    def eq(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> EqualToComparison:
        return EqualToComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    def neq(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> NotEqualToComparison:
        return NotEqualToComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    def gt(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> GreaterThanComparison:
        return GreaterThanComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    def gte(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> GreaterThanOrEqualToComparison:
        return GreaterThanOrEqualToComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    def lt(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> LessThanComparison:
        return LessThanComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    def lte(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> LessThanOrEqualToComparison:
        return LessThanOrEqualToComparison(
            lhs=self, rhs=_one_expression_from(unnamed_expressions, named_expressions)
        )

    @property
    def evaluated_expression(self) -> BaseExpression[N]:
        return self


class NumericLiteralExpression(BaseLiteralExpression[N], NumericBaseExpression):
    pass


class Product(NumericBaseExpression):
    _operator: ClassVar[str | None] = "times"
    _short_operator: ClassVar[str | None] = "*"
    _operands: list[BaseExpression[N]]

    def __init__(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> None:
        super().__init__()
        self._operands = []
        for o in _expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, Product):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def operands(self) -> list[BaseExpression[N]]:
        return self._operands

    @property
    def value(self) -> N:
        return math.prod(o.value for o in self._operands)

    @property
    def reason(self) -> str:
        return " * ".join(f"({o.reason})" for o in self._operands)


class Quotient(NumericBaseExpression):
    _operator: ClassVar[str | None] = "divided by"
    _short_operator: ClassVar[str | None] = "/"
    _dividend: BaseExpression[N]
    _divisor: BaseExpression[N]

    def __init__(self, dividend: BaseExpression[N], divisor: BaseExpression[N]) -> None:
        super().__init__()
        self._dividend = dividend
        self._divisor = divisor

    @property
    def operands(self) -> list[BaseExpression[N]]:
        return [self._dividend, self._divisor]

    @property
    def value(self) -> float:
        return self._dividend.value / self._divisor.value


class Sum(NumericBaseExpression):
    _operator: ClassVar[str | None] = "plus"
    _short_operator: ClassVar[str | None] = "+"
    _operands: list[BaseExpression[N]]

    def __init__(
        self,
        *unnamed_expressions: BaseExpression[N],
        **named_expressions: BaseExpression[N] | N,
    ) -> None:
        super().__init__()
        self._operands = []
        for o in _expressions_from(unnamed_expressions, named_expressions):
            if o._name is not None or not isinstance(o, Sum):
                self._operands.append(o)
            else:
                self._operands.extend(o._operands)

    @property
    def operands(self) -> list[BaseExpression[N]]:
        return self._operands

    @property
    def value(self) -> N:
        return sum(o.value for o in self._operands)


class Difference(NumericBaseExpression):
    _operator: ClassVar[str | None] = "minus"
    _short_operator: ClassVar[str | None] = "-"
    _minuend: BaseExpression[N]
    _subtrahend: BaseExpression[N]

    def __init__(
        self, minuend: BaseExpression[N], subtrahend: BaseExpression[N]
    ) -> None:
        super().__init__()
        self._minuend = minuend
        self._subtrahend = subtrahend

    @property
    def operands(self) -> list[BaseExpression[N]]:
        return [self._minuend, self._subtrahend]

    @property
    def value(self) -> N:
        return self._minuend.value - self._subtrahend.value


class _NumericComparison(BooleanBaseExpression):
    _lhs: BaseExpression[N]
    _rhs: BaseExpression[N]

    def __init__(self, lhs: BaseExpression[N], rhs: BaseExpression[N]) -> None:
        super().__init__()
        self._lhs = lhs
        self._rhs = rhs

    @property
    def operands(self) -> list[BaseExpression[N]]:
        return [self._lhs, self._rhs]


class EqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is equal to"
    _short_operator: ClassVar[str | None] = "=="

    @property
    def value(self) -> bool:
        return self._lhs.value == self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else NotEqualToComparison(self._lhs, self._rhs)


class NotEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is not equal to"
    _short_operator: ClassVar[str | None] = "!="

    @property
    def value(self) -> bool:
        return self._lhs.value != self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else EqualToComparison(self._lhs, self._rhs)


class GreaterThanComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is greater than"
    _short_operator: ClassVar[str | None] = ">"

    @property
    def value(self) -> bool:
        return self._lhs.value > self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else LessThanOrEqualToComparison(self._lhs, self._rhs)


class GreaterThanOrEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is greater than or equal to"
    _short_operator: ClassVar[str | None] = ">="

    @property
    def value(self) -> bool:
        return self._lhs.value >= self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else LessThanComparison(self._lhs, self._rhs)


class LessThanComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is less than"
    _short_operator: ClassVar[str | None] = "<"

    @property
    def value(self) -> bool:
        return self._lhs.value < self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return (
            self if self.value else GreaterThanOrEqualToComparison(self._lhs, self._rhs)
        )


class LessThanOrEqualToComparison(_NumericComparison):
    _operator: ClassVar[str | None] = "is less than or equal to"
    _short_operator: ClassVar[str | None] = "<="

    @property
    def value(self) -> bool:
        return self._lhs.value <= self._rhs.value

    @property
    def evaluated_expression(self) -> _NumericComparison:
        return self if self.value else GreaterThanComparison(self._lhs, self._rhs)
