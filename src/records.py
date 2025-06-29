from typing import Any
from uuid import UUID

EvaluatedExpressionRecordId = UUID


class EvaluatedExpressionRecord:
    id: EvaluatedExpressionRecordId
    name: str
    value: Any
    operator: str


class OperandRecord:
    used_in_evaluated_expression_id: EvaluatedExpressionRecordId
    value: EvaluatedExpressionRecordId | Any
