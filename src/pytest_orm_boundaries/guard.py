"""Django boundary guard: the aggregate-crossing rule and the query
interception that enforces it.

Patches SQLCompiler.execute_sql to check each query; violations from ignored
call sites are swallowed, and stale ignores are reported.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_orm_boundaries.ignores import IgnoreTracker, find_source_files_in_stack
from pytest_orm_boundaries.read_config import (
    load_aggregates_from_config,
    load_ignored_files_from_config,
)

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db.models.sql.query import Query


class BoundaryViolation(Exception):
    """Raised when a query joins models from more than one aggregate."""


class BoundaryGuard:
    """Intercepts Django's executed queries and enforces the aggregate rule."""

    def __init__(
        self, *, aggregates_config: dict[str, str], ignore_tracker: IgnoreTracker
    ) -> None:
        self._aggregates_config = aggregates_config
        self._tracker = ignore_tracker
        self._original_runner: Callable[..., Any] | None = None

    def install(self) -> None:
        from django.db.models.sql.compiler import SQLCompiler

        original_runner = SQLCompiler.execute_sql
        self._original_runner = original_runner

        def patched_execute_sql(compiler, *args, **kwargs):
            self._check_query(query=compiler.query)
            return original_runner(compiler, *args, **kwargs)

        SQLCompiler.execute_sql = patched_execute_sql

    def restore_original_runner(self) -> None:
        from django.db.models.sql.compiler import SQLCompiler

        SQLCompiler.execute_sql = self._original_runner

    def find_stale_patterns(self) -> list[str]:
        return self._tracker.find_stale_patterns()

    def _check_query(self, *, query: Query) -> None:
        """Raise BoundaryViolation unless the query is clean or ignored."""
        file_paths: list[str] | None = None
        if self._tracker.is_active:
            file_paths = find_source_files_in_stack(root=self._tracker.root)
            self._tracker.mark_seen(file_paths=file_paths)

        table_to_model = _map_tables_to_models()
        labels = [
            table_to_model[table.table_name]._meta.label
            for table in query.alias_map.values()
            if table.table_name in table_to_model
        ]

        try:
            self._check_boundaries(labels=labels)
        except BoundaryViolation:
            if file_paths is None or not self._tracker.has_ignore_for(
                file_paths=file_paths
            ):
                raise
            self._tracker.mark_used(file_paths=file_paths)

    def _check_boundaries(self, *, labels: Iterable[str]) -> None:
        aggregate_by_label = {
            label: aggregate
            for label in labels
            if (aggregate := self._aggregates_config.get(label.lower())) is not None
        }
        aggregates = set(aggregate_by_label.values())
        if len(aggregates) <= 1:
            return

        crossed = ", ".join(sorted(aggregates))
        joined = ", ".join(sorted(aggregate_by_label.keys()))
        raise BoundaryViolation(
            f"aggregate boundaries crossed ({crossed}); joined models: {joined}"
        )


def build_guard(*, rootpath: Path, config_path: Path) -> BoundaryGuard | None:
    aggregates_by_model = load_aggregates_from_config(path=config_path)
    if not aggregates_by_model:
        return None

    ignore_patterns = load_ignored_files_from_config(path=config_path)
    tracker = IgnoreTracker(patterns=ignore_patterns, root=rootpath)

    return BoundaryGuard(aggregates_config=aggregates_by_model, ignore_tracker=tracker)


@functools.cache
def _map_tables_to_models() -> dict[str, type[Model]]:
    """Map db_table -> model class for every installed model."""
    from django.apps import apps

    return {model._meta.db_table: model for model in apps.get_models()}
