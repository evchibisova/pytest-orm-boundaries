"""Track aggregate crossings: apply the rule to models and accumulate the crossings found."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_orm_boundaries.callstack import (
    ProjectStackFrame,
    find_frames_inside_project,
    select_callers_for_report,
)
from pytest_orm_boundaries.xdist_state import (
    SerializedTrackerState,
    iter_crossing_updates,
    matched_ignore_patterns,
    serialize_tracker_state,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pytest_orm_boundaries.allows import AllowList
    from pytest_orm_boundaries.ignores import IgnoreTracker


@dataclass
class CrossingRecord:
    """One execution site, its distinct caller paths, and affected tests."""

    execution_frame: ProjectStackFrame
    crossed_aggregates: tuple[str, ...]  # ("order", "payment")
    involved_models: tuple[str, ...]  # ("order.Invoice", "payrolls.IncomePayment")
    tests: set[str] = field(default_factory=set)
    caller_paths: dict[tuple[ProjectStackFrame, ...], set[str]] = field(
        default_factory=dict
    )


class CrossingTracker:
    """Checks label sets against the aggregate rule and records the crossings,
    skipping allowed and ignored files and naming each crossing's call place and
    test."""

    def __init__(
        self,
        *,
        aggregates_config: dict[str, str],
        allow_list: AllowList,
        ignore_tracker: IgnoreTracker,
        root: Path,
    ) -> None:
        self._aggregates_config = aggregates_config
        self._allow_list = allow_list
        self._ignore_tracker = ignore_tracker
        self._root_path = Path(root)
        self._current_test: str | None = None
        self._crossings: dict[tuple[str, int, tuple[str, ...]], CrossingRecord] = {}

    def set_current_test(self, nodeid: str | None) -> None:
        """Remember which test is running so a recorded crossing can name it."""
        self._current_test = nodeid

    def check(self, *, label_sets: Iterable[Iterable[str]]) -> None:
        """Record a crossing for each label set that spans aggregates, unless an
        allow or an ignore covers the call place.

        Allow wins over ignore: an allowed crossing is suppressed without marking
        the ignore used, so an ignore that only overlaps an allow surfaces as
        stale and can be removed as redundant.
        """
        # ``frames`` is the in-project part of the call stack
        frames: list[ProjectStackFrame] | None = None
        file_paths: set[str] | None = None
        if self._allow_list.is_active or self._ignore_tracker.is_active:
            frames = find_frames_inside_project(root=self._root_path)
            file_paths = {frame.file for frame in frames}
            self._ignore_tracker.mark_seen(file_paths=file_paths)

        for labels in label_sets:
            crossing = self.find_crossing(labels=labels)
            if crossing is None:
                continue
            if file_paths is not None:
                if self._allow_list.has_allow_for(file_paths=file_paths):
                    continue
                if self._ignore_tracker.has_ignore_for(file_paths=file_paths):
                    self._ignore_tracker.mark_used(file_paths=file_paths)
                    continue
            if frames is None:
                frames = find_frames_inside_project(root=self._root_path)
            self.add_record(frames=frames, crossing=crossing, test=self._current_test)

    def find_crossing(
        self, *, labels: Iterable[str]
    ) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
        """Return ``(crossed aggregate names, involved model labels)`` if the
        labels span more than one aggregate, else None.

        e.g. ``(("order", "payment"), ("order.Invoice", "payrolls.IncomePayment"))``.

        ``labels`` are model labels.
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

    def add_record(
        self,
        *,
        frames: Sequence[ProjectStackFrame],
        crossing: tuple[tuple[str, ...], tuple[str, ...]],
        test: str | None,
    ) -> None:
        """Merge one crossing into its execution site and caller path."""
        crossed_aggregates, involved_models = crossing
        execution = (
            frames[0]
            if frames
            else ProjectStackFrame(
                file="<unknown>", line_number=0, function="<unknown>"
            )
        )
        key = (execution.file, execution.line_number, crossed_aggregates)
        record = self._crossings.get(key)
        if record is None:
            record = CrossingRecord(
                execution_frame=execution,
                crossed_aggregates=crossed_aggregates,
                involved_models=involved_models,
            )
            self._crossings[key] = record
        else:
            record.involved_models = tuple(
                sorted(set(record.involved_models) | set(involved_models))
            )
            if execution.function != "<unknown>" and (
                record.execution_frame.function == "<unknown>"
                or execution.function < record.execution_frame.function
            ):
                record.execution_frame = execution

        if test is not None:
            record.tests.add(test)

        caller_path = select_callers_for_report(frames=frames, test=test)
        if caller_path:
            path_tests = record.caller_paths.setdefault(caller_path, set())
            if test is not None:
                path_tests.add(test)

    @property
    def crossings(self) -> list[CrossingRecord]:
        """Recorded crossings, most-affecting first."""
        return sorted(
            self._crossings.values(),
            key=lambda v: (
                -len(v.tests),
                v.execution_frame.file,
                v.execution_frame.line_number,
            ),
        )

    def find_stale_patterns(self) -> list[str]:
        """Ignore globs whose file ran but never crossed -- safe to delete."""
        return self._ignore_tracker.find_stale_patterns()

    def serialize_state(self) -> SerializedTrackerState:
        """Encode collected results using only xdist-serializable values."""
        seen, used = self._ignore_tracker.export_matched_patterns()
        return serialize_tracker_state(
            crossings=self.crossings,
            seen_ignore_patterns=seen,
            used_ignore_patterns=used,
        )

    def merge_state(self, state: SerializedTrackerState) -> None:
        """Merge results collected by another process into this tracker."""
        for frames, crossing, test in iter_crossing_updates(state=state):
            self.add_record(frames=frames, crossing=crossing, test=test)
        seen, used = matched_ignore_patterns(state=state)
        self._ignore_tracker.merge_matched_patterns(
            seen=seen,
            used=used,
        )
