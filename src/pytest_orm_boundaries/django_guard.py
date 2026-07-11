"""Django boundary guard: intercepts queries through Django's connection
execute-wrappers and names tables via the app registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_orm_boundaries.guard import BoundaryGuard
from pytest_orm_boundaries.model_resolution import resolve_labels
from pytest_orm_boundaries.sql_parsing import looks_like_data_query

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.backends.base.base import BaseDatabaseWrapper


class DjangoBoundaryGuard(BoundaryGuard):
    """Boundary guard for Django's ORM."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._attached_connections: list[BaseDatabaseWrapper] = []

    def install(self) -> None:
        """Attach to every DB connection: those open now and any opened later
        (each new connection fires ``connection_created``).
        """
        from django.db import connections
        from django.db.backends.signals import connection_created

        connection_created.connect(self._handle_connection_created, weak=False)
        for connection in connections.all(initialized_only=True):
            self._attach_wrapper(connection)

    def uninstall(self) -> None:
        from django.db.backends.signals import connection_created

        connection_created.disconnect(self._handle_connection_created)
        for connection in self._attached_connections:
            try:
                connection.execute_wrappers.remove(self._execute_wrapper)
            except ValueError:
                pass
        self._attached_connections.clear()

    def resolve_labels(self, table_names: Iterable[str]) -> list[str]:
        """Map db tables to ``app_label.Model`` labels via the app registry."""
        return resolve_labels(table_names)

    def _handle_connection_created(
        self, *, connection: BaseDatabaseWrapper, **_
    ) -> None:
        self._attach_wrapper(connection)

    def _attach_wrapper(self, connection: BaseDatabaseWrapper) -> None:
        if self._execute_wrapper not in connection.execute_wrappers:
            connection.execute_wrappers.append(self._execute_wrapper)
            self._attached_connections.append(connection)

    def _execute_wrapper(self, execute, sql, params, many, context):
        if looks_like_data_query(sql):
            self._check_violations_in_query(sql, context["connection"].vendor)
        return execute(sql, params, many, context)
