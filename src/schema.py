from __future__ import annotations

from typing import Any

from sqlalchemy import UUID, String, Uuid, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)
from sqlalchemy.orm.base import NEVER_SET


class OrmDataclass(MappedAsDataclass, kw_only=True):
    def __post_init__(self):
        # https://github.com/sqlalchemy/sqlalchemy/discussions/9383#discussioncomment-10140882
        for relationship_name in inspect(self.__class__).relationships.keys():
            if getattr(self, relationship_name) == NEVER_SET:
                setattr(self, relationship_name, None)
                delattr(self, relationship_name)


class EvaluatedExpressionRecord(DeclarativeBase, OrmDataclass):
    id: Mapped[UUID] = mapped_column(Uuid, default=None)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, default=None)
    name: str | None = mapped_column(String, default=None)
    value: Any = mapped_column(JSONB)
    operator: str = mapped_column(String)

    parent: Mapped[EvaluatedExpressionRecord | None] = relationship(
        default=NEVER_SET, back_populates="children", remote_side=[id], repr=False
    )
    children: Mapped[list[EvaluatedExpressionRecord]] = relationship(
        default_factory=list, back_populates="parent", remote_side=[id], repr=False
    )
