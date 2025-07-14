from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar, Literal, Self
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from schema import EvaluatedExpressionRecord
from utils import get_exactly_one


def _value(x: Expression | Any) -> Any:
    if isinstance(x, Expression):
        return x.value
    else:
        return x


class Expression:
    value: Any
    _id: UUID
    _name: str | None
    _operator: ClassVar[str | None] = None
    _operands: list[Expression]

    def __init__(
        self,
        *unnamed_expressions: tuple[Expression[Any], ...],
        **named_expressions: dict[str, Expression[Any] | Any],
    ) -> None:
        self.value = _handle_expressions(
            unnamed_expressions, named_expressions, allow_multiple=False
        )
        self._id = uuid4()
        self._name = None
        self._operands = []

    def with_name(self, name: str) -> Self:
        self = deepcopy(self)
        self._name = name
        return self

    def and_(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> And:
        return And(
            operands=[
                *self._and_operands,
                *_handle_expressions(unnamed_conditions, named_conditions).conditions,
            ]
        )

    def or_(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> Or:
        return Or(
            conditions=[
                *self._or_operands,
                _handle_expressions(unnamed_conditions, named_conditions).conditions,
            ]
        )

    def if_(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> IncompleteConditional:
        return IncompleteConditional(
            result_if_true=(self.value if type(self) is Expression else self),
            condition=_handle_expressions(unnamed_conditions, named_conditions),
        )

    @property
    def _and_operands(self) -> list[Expression[bool]]:
        return [self]

    @property
    def _or_operands(self) -> list[Expression[bool]]:
        return [self]

    @property
    def evaluated_expression(self) -> Expression:
        return self

    @property
    def evaluated_expression_record(self) -> EvaluatedExpressionRecord:
        return EvaluatedExpressionRecord(
            id=self._id,
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


class Not(Expression):
    _operator: ClassVar[Literal["not"]] = "not"
    _operand: Expression[bool]

    def __init__(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operand = _handle_expressions(unnamed_conditions, named_conditions)

    @property
    def _operands(self) -> list[Expression[bool] | bool]:
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


class And(Expression):
    _operator: ClassVar[Literal["and"]] = "and"
    _operands: list[Expression[bool] | bool]

    def __init__(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = _handle_expressions(
            unnamed_conditions, named_conditions, consolidate_multiple=False
        )

    @property
    def and_operands(self) -> list[Expression[bool] | bool]:
        return self._operands

    @property
    def value(self) -> bool:
        return all(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            And([o.evaluated_expression for o in self._operands])
            if self.value
            else Or(
                [Not(o) for o in self._operands if not o.value]
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


class Or(Expression):
    _operator: ClassVar[Literal["or"]] = "or"
    _operands: list[Expression[bool] | bool]

    def __init__(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> None:
        self._id = uuid4()
        self._name = None
        self._operands = _handle_expressions(
            unnamed_conditions, named_conditions, consolidate_multiple=False
        )

    @property
    def or_operands(self) -> list[Expression[bool] | bool]:
        return self._operands

    @property
    def value(self) -> bool:
        return any(o.value for o in self._operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            Or([o.evaluated_expression for o in self._operands if o.value])
            if self.value
            else And([Not(o) for o in self._operands]).evaluated_expression
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
    _result_if_true: Expression | Any
    _condition: Expression[bool] | bool

    def __init__(
        self, result_if_true: Expression | Any, condition: Expression[bool] | bool
    ) -> None:
        self._result_if_true = result_if_true
        self._condition = condition

    def else_(
        self,
        *unnamed_expressions: tuple[Expression[bool], ...],
        **named_expressions: dict[str, Expression[bool] | bool],
    ) -> Conditional:
        return Conditional(
            self._result_if_true,
            self._condition,
            result_if_false=_handle_expressions(unnamed_expressions, named_expressions),
        )


class Conditional(Expression):
    _result_if_true: Expression | Any
    _condition: Expression[bool]
    _result_if_false: Expression | Any

    def __init__(
        self,
        result_if_true: Expression | Any,
        condition: Expression[bool] | bool,
        result_if_false: Expression | Any,
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
    unnamed_expressions: tuple[Expression[bool], ...],
    named_expressions: dict[str, Expression[bool] | bool],
    allow_multiple: bool = True,
    consolidate_multiple: bool = True,
) -> Expression[bool] | list[Expression[bool]]:
    expressions = list(unnamed_expressions) + [
        (e if isinstance(e, Expression) else Expression(e)).with_name(n)
        for n, e in named_expressions.items()
    ]
    if len(expressions) == 0:
        raise Exception
    elif len(expressions) == 1:
        return get_exactly_one(expressions)
    elif allow_multiple:
        if consolidate_multiple:
            return And(expressions)
        else:
            return expressions
    else:
        raise Exception
