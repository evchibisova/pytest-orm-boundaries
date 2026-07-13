"""Django boundary guard: watches the queries a test suite executes and checks crossing.

Two sources of crossings: the SQL of each executed query, and the relation path
of each ``prefetch_related``.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_orm_boundaries.crossings import CrossingTracker, SerializedTrackerState
from pytest_orm_boundaries.model_resolution import resolve_labels
from pytest_orm_boundaries.prefetch_resolution import resolve_prefetch_step_models
from pytest_orm_boundaries.sql_parsing import extract_table_names, looks_like_data_query

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

    from pytest_orm_boundaries.allows import AllowList
    from pytest_orm_boundaries.crossings import CrossingRecord
    from pytest_orm_boundaries.ignores import IgnoreTracker


@dataclass
class _HookState:
    """On/off switch for one installed prefetch wrapper.

    We monkey-patch Django's ``prefetch_related_objects``. On uninstall we
    restore the original when our wrapper is still on top - but if another tool
    wrapped it above ours, that tool holds a reference to our wrapper and we
    can't take it out of the chain. So instead of removing it we set ``active``
    to False: the wrapper keeps being called but does nothing.
    """

    active: bool


class BoundaryGuard:
    """Records aggregate crossings in the queries a test suite executes."""

    def __init__(
        self,
        *,
        aggregates_config: dict[str, str],
        allow_list: AllowList,
        ignore_tracker: IgnoreTracker,
        root: Path,
    ) -> None:
        self._tracker = CrossingTracker(
            aggregates_config=aggregates_config,
            allow_list=allow_list,
            ignore_tracker=ignore_tracker,
            root=root,
        )
        self._attached_connections: list[BaseDatabaseWrapper] = []
        self._original_prefetch = None
        self._prefetch_wrapper = None
        self._prefetch_hook_state: _HookState | None = None

    def install(self) -> None:
        """Attach to every DB connection: those open now and any opened later
        (each new connection fires ``connection_created``).
        """
        from django.db import connections
        from django.db.backends.signals import connection_created

        connection_created.connect(self._handle_connection_created, weak=False)
        for connection in connections.all(initialized_only=True):
            self._attach_wrapper(connection)
        self._install_prefetch_hook()

    def uninstall(self) -> None:
        from django.db.backends.signals import connection_created

        self._remove_prefetch_hook()
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

    def _install_prefetch_hook(self) -> None:
        """Wrap django ``prefetch_related_objects`` so each prefetch reports the
        models it walks between.
        """
        import django.db.models.query as query_module

        if self._prefetch_wrapper is not None:
            # Already installed. A second install would capture our own wrapper
            # as ``original`` and orphan the first _HookState
            return

        original = query_module.prefetch_related_objects
        # hook can be switched off even when it can't be removed from the chain.
        state = _HookState(active=True)
        # strong ref is config.stash[guard_key]
        guard_ref = weakref.ref(self)

        @wraps(original)
        def prefetch_with_check(model_instances, *lookups):
            result = original(model_instances, *lookups)
            guard = guard_ref()
            if state.active and guard is not None:
                guard._handle_prefetch(
                    model_instances=model_instances, lookups=lookups
                )
            return result

        self._prefetch_hook_state = state
        self._original_prefetch = original
        self._prefetch_wrapper = prefetch_with_check
        query_module.prefetch_related_objects = prefetch_with_check

    def _remove_prefetch_hook(self) -> None:
        import django.db.models.query as query_module

        if self._prefetch_wrapper is None:
            return
        # Disable our hook unconditionally. Restore the previous callable only
        # when ours is still topmost; otherwise another wrapper may still
        # reference it, and ours stays in the chain as an inert no-op.
        self._prefetch_hook_state.active = False
        if query_module.prefetch_related_objects is self._prefetch_wrapper:
            query_module.prefetch_related_objects = self._original_prefetch
        self._prefetch_hook_state = None
        self._prefetch_wrapper = None
        self._original_prefetch = None

    def _execute_wrapper(self, execute, sql, params, many, context):
        if looks_like_data_query(sql):
            self._handle_query(sql, context["connection"].vendor)
        return execute(sql, params, many, context)

    def set_current_test(self, nodeid: str | None) -> None:
        """Remember which test is running so a recorded crossing can name it."""
        self._tracker.set_current_test(nodeid)

    @property
    def crossings(self) -> list[CrossingRecord]:
        return self._tracker.crossings

    def find_stale_patterns(self) -> list[str]:
        return self._tracker.find_stale_patterns()

    def serialize_state(self) -> SerializedTrackerState:
        """Return process-local results for transport to an xdist controller."""
        return self._tracker.serialize_state()

    def merge_state(self, state: SerializedTrackerState) -> None:
        """Merge results received by the xdist controller from one worker."""
        self._tracker.merge_state(state)

    def _handle_query(self, sql: str, vendor: str) -> None:
        """Map one executed data query to its table labels and check them."""
        table_names = extract_table_names(sql, vendor)
        if table_names is None:
            return
        labels = resolve_labels(table_names)
        self._tracker.check(label_sets=[labels])

    def _handle_prefetch(self, *, model_instances, lookups) -> None:
        """Map one prefetch to the model pair per relation step and check them."""
        if not model_instances:
            return
        from django.db.models import Model

        first = model_instances[0]
        if not isinstance(first, Model):
            return
        source_model = type(first)
        step_model_pairs = resolve_prefetch_step_models(
            source_model=source_model, lookups=lookups
        )
        if not step_model_pairs:
            return
        self._tracker.check(label_sets=step_model_pairs)
