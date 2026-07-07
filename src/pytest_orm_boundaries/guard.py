"""Django boundary guard: the aggregate-crossing rule and the query
interception that records crossings.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_orm_boundaries.call_stack import find_in_project_frames
from pytest_orm_boundaries.ignores import IgnoreTracker
from pytest_orm_boundaries.read_config import (
    load_aggregates_from_config,
    load_ignored_files_from_config,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Any

    from django.db.models import Model
    from django.db.models.sql.query import Query


@dataclass
class ViolationRecord:
    """One offending call place and the tests that reached it.

    Grouped by call place so a crossing shared by many tests is one entry,
    not one line per test.
    """

    file: str
    line_number: int
    crossed_aggregates: tuple[str, ...]  # ("order", "payment")
    joined_models: tuple[str, ...]  # ("order.Invoice", "payrolls.IncomePayment")
    tests: set[str] = field(default_factory=set)


class BoundaryGuard:
    """Intercepts Django's executed queries and records aggregate crossings."""

    def __init__(
        self,
        *,
        aggregates_config: dict[str, str],
        ignore_tracker: IgnoreTracker,
        root: Path,
    ) -> None:
        self._aggregates_config = aggregates_config
        self._ignore_tracker = ignore_tracker
        self._root = Path(root)
        self._original_execute_sql: Callable[..., Any] | None = None
        self._current_test: str | None = None
        self._violations: dict[tuple[str, int, tuple[str, ...]], ViolationRecord] = {}

    def install(self) -> None:
        from django.db.models.sql.compiler import SQLCompiler

        original_execute_sql = SQLCompiler.execute_sql
        self._original_execute_sql = original_execute_sql

        def patched_execute_sql(compiler, *args, **kwargs):
            self._handle_query(query=compiler.query)
            return original_execute_sql(compiler, *args, **kwargs)

        SQLCompiler.execute_sql = patched_execute_sql

    def uninstall(self) -> None:
        from django.db.models.sql.compiler import SQLCompiler

        SQLCompiler.execute_sql = self._original_execute_sql

    def set_current_test(self, nodeid: str | None) -> None:
        """Remember which test is running so a recorded crossing can name it."""
        self._current_test = nodeid

    @property
    def violations(self) -> list[ViolationRecord]:
        """Recorded crossings, most-affecting first (then by call place)."""
        return sorted(
            self._violations.values(),
            key=lambda v: (-len(v.tests), v.file, v.line_number),
        )

    def find_stale_patterns(self) -> list[str]:
        return self._ignore_tracker.find_stale_patterns()

    def _handle_query(self, *, query: Query) -> None:
        """Handle one executed query: gather stack context, apply the aggregate
        rule, and record a crossing (unless it's clean or its place is ignored).
        """
        # ``frames`` is the in-project part of this query's call stack,
        # used by the ignore/stale check and the report.
        frames: list[tuple[str, int]] | None = None
        file_paths: list[str] | None = None
        if self._ignore_tracker.is_active:
            frames = find_in_project_frames(root=self._root)
            file_paths = self._extract_file_paths(frames)
            self._ignore_tracker.mark_seen(file_paths=file_paths)

        labels = self._read_labels(query=query)
        crossing = self._find_crossing(labels=labels)
        if crossing is None:
            return

        if file_paths is not None and self._ignore_tracker.has_ignore_for(
            file_paths=file_paths
        ):
            self._ignore_tracker.mark_used(file_paths=file_paths)
            return

        if frames is None:
            frames = find_in_project_frames(root=self._root)
        self._record_violation(
            call_place=frames[0] if frames else None, crossing=crossing
        )

    def _read_labels(self, *, query: Query) -> list[str]:
        """Model labels of the tables the query actually reads.

        A filter on a foreign-key id reads a column already on the current
        table, so the table it points to isn't read -- and isn't counted.
        """
        table_to_model = _map_tables_to_models()
        return [
            table_to_model[table.table_name]._meta.label
            for alias, table in query.alias_map.items()
            if table.table_name in table_to_model
            and query.alias_refcount.get(alias, 0) > 0
        ]

    def _find_crossing(
        self, *, labels: Iterable[str]
    ) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
        """Return ``(crossed aggregate names, joined model labels)`` if the query
        crosses a boundary, else None.

        e.g. ``(("order", "payment"), ("order.Invoice", "payrolls.IncomePayment"))``.
        """
        aggregate_by_label = {
            label: aggregate
            for label in labels
            if (aggregate := self._aggregates_config.get(label.lower())) is not None
        }
        aggregates = set(aggregate_by_label.values())
        if len(aggregates) <= 1:
            return None
        return tuple(sorted(aggregates)), tuple(sorted(aggregate_by_label.keys()))

    def _record_violation(
        self,
        *,
        call_place: tuple[str, int] | None,
        crossing: tuple[tuple[str, ...], tuple[str, ...]],
    ) -> None:
        crossed_aggregates, joined_models = crossing
        file, line = call_place if call_place is not None else ("<unknown>", 0)
        key = (file, line, crossed_aggregates)
        record = self._violations.get(key)
        if record is None:
            record = ViolationRecord(
                file=file,
                line_number=line,
                crossed_aggregates=crossed_aggregates,
                joined_models=joined_models,
            )
            self._violations[key] = record
        if self._current_test is not None:
            record.tests.add(self._current_test)

    @staticmethod
    def _extract_file_paths(frames: Iterable[tuple[str, int]]) -> set[str]:
        return {path for path, _ in frames}


def build_guard(*, rootpath: Path, config_path: Path) -> BoundaryGuard | None:
    aggregates_by_model = load_aggregates_from_config(path=config_path)
    if not aggregates_by_model:
        return None

    ignore_patterns = load_ignored_files_from_config(path=config_path)
    tracker = IgnoreTracker(patterns=ignore_patterns)

    return BoundaryGuard(
        aggregates_config=aggregates_by_model, ignore_tracker=tracker, root=rootpath
    )


@functools.cache
def _map_tables_to_models() -> dict[str, type[Model]]:
    """Map db_table -> model class for every installed model."""
    from django.apps import apps

    return {model._meta.db_table: model for model in apps.get_models()}
