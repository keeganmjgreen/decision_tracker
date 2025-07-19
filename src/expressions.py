from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar, Self, cast
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from schema import EvaluatedExpressionRecord
from utils import get_exactly_one


def _value(x: Expression[Any] | Any) -> Any:
    if isinstance(x, Expression):
        return x.value
    else:
        return x


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

    def with_name(self, name: str) -> Self:
        self = deepcopy(self)
        self._name = name
        return self

    def if_(
        self,
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> IncompleteConditional:
        condition = _handle_expressions(
            unnamed_conditions, named_conditions, multiple_output=False
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


class BooleanExpression(Expression[bool]):
    _operands: list[BooleanExpression]

    def and_(
        self,
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> And:
        return And(
            self,
            *cast(
                list[BooleanExpression],
                _handle_expressions(
                    unnamed_conditions, named_conditions, multiple_output=True
                ),
            ),
        )

    def or_(
        self,
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> Or:
        return Or(
            self,
            cast(
                BooleanExpression,
                _handle_expressions(
                    unnamed_conditions, named_conditions, multiple_output=False
                ),
            ),
        )

    @property
    def _and_operands(self) -> list[BooleanExpression]:
        return [self]

    @property
    def _or_operands(self) -> list[BooleanExpression]:
        return [self]

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return self


class Not(BooleanExpression):
    _operator: ClassVar[str | None] = "not"
    _operand: BooleanExpression

    def __init__(
        self,
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operand = cast(
            BooleanExpression,
            _handle_expressions(
                unnamed_conditions, named_conditions, multiple_output=False
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
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in cast(
            list[BooleanExpression],
            _handle_expressions(unnamed_conditions, named_conditions),
        ):
            if o._name is not None:
                self._operands.append(o)
            else:
                self._operands.extend(o._and_operands)

    @property
    def _and_operands(self) -> list[BooleanExpression]:
        return self._operands

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
        *unnamed_conditions: BooleanExpression,
        **named_conditions: BooleanExpression | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = []
        for o in cast(
            list[BooleanExpression],
            _handle_expressions(unnamed_conditions, named_conditions),
        ):
            if o._name is not None:
                self._operands.append(o)
            else:
                self._operands.extend(o._or_operands)

    @property
    def _or_operands(self) -> list[BooleanExpression]:
        return self._operands

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
            _value(self._result_if_true)
            if _value(self._condition)
            else _value(self._result_if_false)
        )

    @property
    def evaluated_expression(self) -> BooleanExpression:
        return self._condition.evaluated_expression

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.evaluated_expression.reason
        )


def _handle_expressions(
    unnamed_expressions: tuple[BooleanExpression, ...],
    named_expressions: dict[str, BooleanExpression | bool],
    allow_multiple_input: bool = True,
    multiple_output: bool = True,
) -> BooleanExpression | list[BooleanExpression]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, BooleanExpression) else BooleanExpression(**{n: e}))
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
