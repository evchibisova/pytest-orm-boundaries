"""SQLAlchemy boundary guard: intercepts queries through the Engine's
``before_cursor_execute`` event and names tables by their SQL table name.

SQLAlchemy has no single global model registry (mappings live per-``Base``, and
plenty of code reaches the DB through Core or ``text()`` with no mapped class at
all). The one handle present in every executed statement is the table name, so
aggregates are declared by table name and label resolution is the identity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_orm_boundaries.guard import BoundaryGuard
from pytest_orm_boundaries.sql_parsing import looks_like_data_query

if TYPE_CHECKING:
    from collections.abc import Iterable


class SQLAlchemyBoundaryGuard(BoundaryGuard):
    """Boundary guard for SQLAlchemy's Core/ORM engine."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Hold one bound-method reference so listen and remove target the same
        # object -- SQLAlchemy keys listeners by identity.
        self._listener = self._handle_cursor_execute

    def install(self) -> None:
        """Listen on the Engine class so every engine the suite builds is covered."""
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        event.listen(Engine, "before_cursor_execute", self._listener)

    def uninstall(self) -> None:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        if event.contains(Engine, "before_cursor_execute", self._listener):
            event.remove(Engine, "before_cursor_execute", self._listener)

    def resolve_labels(self, table_names: Iterable[str]) -> list[str]:
        """The SQL table name is the aggregate-member label; nothing to resolve."""
        return list(table_names)

    def _handle_cursor_execute(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        if looks_like_data_query(statement):
            self._check_violations_in_query(statement, conn.dialect.name)
