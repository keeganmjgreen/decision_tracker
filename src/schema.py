from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Column, ForeignKey, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase, MappedAsDataclass, kw_only=True):
    pass


# Many-to-many association table.
# See https://docs.sqlalchemy.org/en/20/orm/join_conditions.html#self-referential-many-to-many.
association_table = Table(
    "evaluated_expression_association",
    Base.metadata,
    Column(
        "parent_id", Uuid(), ForeignKey("evaluated_expression.id"), primary_key=True
    ),
    Column("child_id", Uuid(), ForeignKey("evaluated_expression.id"), primary_key=True),
)


class EvaluatedExpressionRecord(Base):
    __tablename__ = "evaluated_expression"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, default=None, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, default=None)
    value: Mapped[Any] = mapped_column(JSONB)  # type: ignore
    operator: Mapped[str | None] = mapped_column(Text)  # type: ignore

    children: Mapped[list[EvaluatedExpressionRecord]] = relationship(
        "EvaluatedExpressionRecord",
        default_factory=list,
        secondary=association_table,
        primaryjoin=(id == association_table.c.parent_id),
        secondaryjoin=(id == association_table.c.child_id),
        back_populates="parents",
        repr=False,
    )
    parents: Mapped[list[EvaluatedExpressionRecord]] = relationship(
        "EvaluatedExpressionRecord",
        default_factory=list,
        secondary=association_table,
        primaryjoin=(id == association_table.c.child_id),
        secondaryjoin=(id == association_table.c.parent_id),
        back_populates="children",
        repr=False,
    )
