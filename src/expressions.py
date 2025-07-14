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

    def __init__(
        self,
        *unnamed_expressions: Expression[T],
        **named_expressions: Expression[T] | T,
    ) -> None:
        value = _handle_expressions(
            unnamed_expressions,
            named_expressions,
            allow_multiple_input=False,
            multiple_output=False,
        )
        self.value = cast(T, value)
        self._id = uuid4()
        self._name = None
        self._operands = []

    def with_name(self, name: str) -> Self:
        self = deepcopy(self)
        self._name = name
        return self

    def if_(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> IncompleteConditional:
        condition = _handle_expressions(
            unnamed_conditions, named_conditions, multiple_output=False
        )
        return IncompleteConditional(
            result_if_true=(self.value if type(self) is Expression else self),
            condition=cast(Expression[bool], condition),
        )

    @property
    def evaluated_expression(self) -> Expression[Any]:
        return self

    @property
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        return EvaluatedExpressionRecord(
            id=self._id,  # type: ignore
            name=self._name,
            value=self.value,
            operator=self._operator,
            children=[o.evaluated_expression_record for o in self._operands],
        )

    @property
    def reason(self) -> str:
        return f"{self._name} := {self.value}"

    def __str__(self) -> str:
        return self.reason

    def to_db(self, db_engine: Engine) -> None:
        with Session(db_engine) as session:
            session.add(self.evaluated_expression_record)  # Also adds children.
            session.commit()


class BooleanExpression(Expression[bool]):
    def and_(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> And:
        return And(
            *self._and_operands,
            *cast(
                Expression[bool],
                _handle_expressions(
                    unnamed_conditions, named_conditions, multiple_output=False
                ),
            )._operands,
        )

    def or_(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> Or:
        return Or(
            *self._or_operands,
            cast(
                Expression[bool],
                _handle_expressions(
                    unnamed_conditions, named_conditions, multiple_output=False
                ),
            ),
        )

    @property
    def _and_operands(self) -> list[Expression[bool]]:
        return [self]

    @property
    def _or_operands(self) -> list[Expression[bool]]:
        return [self]


class Not(Expression[bool]):
    _operator: ClassVar[str | None] = "not"
    _operand: Expression[bool]

    def __init__(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        operand = _handle_expressions(
            unnamed_conditions, named_conditions, multiple_output=False
        )
        self._operand = cast(Expression[bool], operand)

    @property
    def _operands(self) -> list[Expression[bool]]:
        return [self._operand]

    @property
    def value(self) -> bool:
        return not self._operand.value

    @property
    def evaluated_expression(self) -> Expression[bool]:
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


class And(Expression[bool]):
    _operator: ClassVar[str | None] = "and"
    _operands: list[Expression[bool]]

    def __init__(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        operands = _handle_expressions(unnamed_conditions, named_conditions)
        self._operands = cast(list[Expression[bool]], operands)

    @property
    def and_operands(self) -> list[Expression[bool]]:
        return self._operands

    @property
    def value(self) -> bool:
        return all(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
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


class Or(Expression[bool]):
    _operator: ClassVar[str | None] = "or"
    _operands: list[Expression[bool]]

    def __init__(
        self,
        *unnamed_conditions: Expression[bool],
        **named_conditions: Expression[bool] | bool,
    ) -> None:
        self._id = uuid4()
        self._name = None
        operands = _handle_expressions(unnamed_conditions, named_conditions)
        self._operands = cast(list[Expression[bool]], operands)

    @property
    def or_operands(self) -> list[Expression[bool]]:
        return self._operands

    @property
    def value(self) -> bool:
        return any(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            Or(*[o.evaluated_expression for o in self._operands if o.value])
            if self.value
            else And(*[Not(o) for o in self._operands]).evaluated_expression
        )

    @property
    def reason(self) -> str:
        return (
            " or ".join(f"({o.reason})" for o in self._operands)
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
    _condition: Expression[bool]

    def __init__(
        self, result_if_true: Expression[Any] | Any, condition: Expression[bool]
    ) -> None:
        self._result_if_true = result_if_true
        self._condition = condition

    def else_(
        self,
        *unnamed_expressions: Expression[bool],
        **named_expressions: Expression[bool] | bool,
    ) -> Conditional:
        return Conditional(
            self._result_if_true,
            self._condition,
            result_if_false=_handle_expressions(
                unnamed_expressions,
                named_expressions,
                allow_multiple_input=False,
                multiple_output=False,
            ),
        )


class Conditional(Expression[Any]):
    _result_if_true: Expression[Any] | Any
    _condition: Expression[bool]
    _result_if_false: Expression[Any] | Any

    def __init__(
        self,
        result_if_true: Expression[Any] | Any,
        condition: Expression[bool],
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
    def evaluated_expression(self) -> Expression[bool]:
        return self._condition.evaluated_expression

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + self.evaluated_expression.reason
        )


def _handle_expressions(
    unnamed_expressions: tuple[Expression[Any], ...],
    named_expressions: dict[str, Expression[Any] | Any],
    allow_multiple_input: bool = True,
    multiple_output: bool = True,
) -> Expression[Any] | list[Expression[Any]]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, Expression) else Expression(e)).with_name(n)
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
