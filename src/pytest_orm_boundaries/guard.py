"""Django boundary guard: applies the aggregate-crossing rule to the queries a
test suite executes and records the crossings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_orm_boundaries.callstack import find_frames_inside_project
from pytest_orm_boundaries.config import (
    load_aggregates_from_config,
    load_ignored_files_from_config,
)
from pytest_orm_boundaries.ignores import IgnoreTracker
from pytest_orm_boundaries.model_resolution import resolve_labels
from pytest_orm_boundaries.sql_parsing import extract_table_names, looks_like_data_query

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.backends.base.base import BaseDatabaseWrapper


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
    """Records aggregate crossings in the queries a test suite executes."""

    def __init__(
        self,
        *,
        aggregates_config: dict[str, str],
        ignore_tracker: IgnoreTracker,
        root: Path,
    ) -> None:
        self._aggregates_config = aggregates_config
        self._ignore_tracker = ignore_tracker
        self._root_path = Path(root)
        self._current_test: str | None = None
        self._violations: dict[tuple[str, int, tuple[str, ...]], ViolationRecord] = {}
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

    def _check_violations_in_query(self, sql: str, vendor: str) -> None:
        """Handle one executed data query: gather stack context, apply the
        aggregate rule, and record a crossing (unless it's clean or ignored).
        """
        # ``frames`` is the in-project part of this query's call stack,
        # used by the ignore/stale check and the report.
        frames: list[tuple[str, int]] | None = None
        file_paths: set[str] | None = None
        if self._ignore_tracker.is_active:
            frames = find_frames_inside_project(root=self._root_path)
            file_paths = {path for path, _ in frames}
            self._ignore_tracker.mark_seen(file_paths=file_paths)

        table_names = extract_table_names(sql, vendor)
        if table_names is None:  # unparseable data query -- skip it (see ROADMAP)
            return
        labels = resolve_labels(table_names)
        crossing = self._find_crossing(labels=labels)
        if crossing is None:
            return

        if file_paths is not None and self._ignore_tracker.has_ignore_for(
            file_paths=file_paths
        ):
            self._ignore_tracker.mark_used(file_paths=file_paths)
            return

        if frames is None:
            frames = find_frames_inside_project(root=self._root_path)
        self._record_violation(
            call_place=frames[0] if frames else None, crossing=crossing
        )

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


def build_guard(*, rootpath: Path, config_path: Path) -> BoundaryGuard | None:
    aggregates_by_model = load_aggregates_from_config(path=config_path)
    if not aggregates_by_model:
        return None

    ignore_patterns = load_ignored_files_from_config(path=config_path)
    tracker = IgnoreTracker(patterns=ignore_patterns)

    return BoundaryGuard(
        aggregates_config=aggregates_by_model, ignore_tracker=tracker, root=rootpath
    )
