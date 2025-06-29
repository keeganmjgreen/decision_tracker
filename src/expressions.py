from __future__ import annotations

import dataclasses
from copy import deepcopy
from typing import Any, ClassVar, Self
from uuid import UUID, uuid4

import records as records
from utils import get_exactly_one


def _value(x: Expression | Any) -> Any:
    if isinstance(x, Expression):
        return x.value
    else:
        return x


class Expression:
    value: Any
    _id: UUID
    _name: str | None = None

    def __init__(
        self,
        *unnamed_expressions: tuple[Expression[Any], ...],
        **named_expressions: dict[str, Expression[Any] | Any],
    ) -> None:
        self.value = _handle_expressions(
            unnamed_expressions, named_expressions, allow_multiple=False
        )
        self._id = uuid4()

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
    def flattened(
        self,
    ) -> tuple[list[records.EvaluatedExpressionRecord], list[records.OperandRecord]]:
        evaluated_expression_records = [
            records.EvaluatedExpressionRecord(
                id=self._id,
                name=self.name,
                operand=self.operand,
            )
        ]
        operand_records = [
            records.OperandRecord(
                used_in_evaluated_expression_id=self._id,
                value=(self.value or o.id),
            )
            for o in self.operands
        ]
        for operand in self.operands:
            x, y = operand.flattened
            evaluated_expression_records.extend(x)
            operand_records.extend(y)
        return evaluated_expression_records, operand_records

    def __str__(self):
        return f"{self._name} := {self.value}"


class Not(Expression):
    operator: ClassVar[str] = "not"
    operand: Expression[bool]

    def __init__(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> None:
        self.operand = _handle_expressions(unnamed_conditions, named_conditions)
        self._id = uuid4()

    @property
    def operands(self) -> list[Expression[bool] | bool]:
        return [self.operand]

    @property
    def value(self) -> bool:
        return not self.operand.value

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            Or(operands=[Not(o) for o in self.operand.operands])
            if isinstance(self.operand, And)
            else (
                self.operand.operand
                if isinstance(self.operand, Not)
                else Not(self.operand)
            )
        )

    def __str__(self):
        return (
            f"{self._name} := {self.value} because {self._name} := "
            if self._name
            else ""
        ) + f"!({self.operand})"


class And(Expression):
    operator: ClassVar[str] = "and"
    operands: list[Expression[bool] | bool]

    def __init__(
        self,
        *unnamed_conditions: tuple[Expression[bool], ...],
        **named_conditions: dict[str, Expression[bool] | bool],
    ) -> None:
        self.operands = _handle_expressions(
            unnamed_conditions, named_conditions, consolidate_multiple=False
        )
        self._id = uuid4()

    @property
    def and_operands(self) -> list[Expression[bool] | bool]:
        return self.operands

    @property
    def value(self) -> bool:
        return all(o.value for o in self.operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
        x = And([o.evaluated_expression for o in self.operands])
        return x if self.value else Not(x).evaluated_expression

    def __str__(self):
        return (
            f"{self._name} := {self.value} because {self._name} := "
            if self._name
            else ""
        ) + (
            " and ".join(f"({o})" for o in self.operands)
            if self.value
            else str(self.evaluated_expression)
        )


@dataclasses.dataclass
class Or(Expression):
    operator: ClassVar[str] = "or"
    operands: list[Expression[bool] | bool]

    def __init__(self, operands: Expression[bool] | bool) -> None:
        self.operands = operands
        self._id = uuid4()

    @property
    def or_operands(self) -> list[Expression[bool] | bool]:
        return self.operands

    @property
    def value(self) -> bool:
        return any(o.value for o in self.operands)

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            next(o.evaluated_expression for o in self.operands if o.value)
            if self.value
            else Not(Or([o.evaluated_expression for o in self.operands]))
        )

    def __str__(self):
        return (
            f"{self._name} := {self.value} because {self._name} := "
            if self._name
            else ""
        ) + (
            " or ".join(f"({o})" for o in self.operands)
            if self.value
            else str(self.evaluated_expression)
        )


@dataclasses.dataclass
class IncompleteConditional:
    result_if_true: Expression
    condition: Expression[bool] | bool

    def __init__(
        self, result_if_true: Expression, condition: Expression[bool] | bool
    ) -> None:
        self.result_if_true = result_if_true
        self.condition = condition

    def else_(
        self,
        *unnamed_expressions: tuple[Expression[bool], ...],
        **named_expressions: dict[str, Expression[bool] | bool],
    ) -> Conditional:
        return Conditional(
            self.result_if_true,
            self.condition,
            result_if_false=_handle_expressions(unnamed_expressions, named_expressions),
        )


@dataclasses.dataclass
class Conditional(Expression):
    result_if_true: Expression | Any
    condition: Expression[bool]
    result_if_false: Expression | Any

    @property
    def value(self) -> bool:
        return (
            _value(self.result_if_true)
            if _value(self.condition)
            else _value(self.result_if_false)
        )

    @property
    def evaluated_expression(self) -> Expression[bool]:
        return (
            self.condition.evaluated_expression
            if _value(self.condition)
            else Not(
                Expression(True).with_name(self.condition._name)
                if type(self.condition) is Expression
                else self.condition.evaluated_expression
            )
        )

    def __str__(self):
        return (
            (f"{self._name} := " if self._name else "")
            + f"{self.value} because "
            + str(self.evaluated_expression)
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
