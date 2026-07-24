"""Encode crossing tracker state for transport between pytest-xdist processes."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from pytest_orm_boundaries.callstack import ProjectStackFrame

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from pytest_orm_boundaries.crossings import CrossingRecord

_Crossing = tuple[tuple[str, ...], tuple[str, ...]]
_CrossingUpdate = tuple[tuple[ProjectStackFrame, ...], _Crossing, str | None]


class _SerializedFrame(TypedDict):
    """One project frame encoded for xdist's worker channel."""

    file: str
    line_number: int
    function: str


class _SerializedCallerPath(TypedDict):
    """One caller path and the tests that reached it."""

    frames: list[_SerializedFrame]
    tests: list[str]


class _SerializedCrossing(TypedDict):
    """One crossing encoded using values supported by xdist's worker channel."""

    execution_frame: _SerializedFrame
    crossed_aggregates: list[str]
    involved_models: list[str]
    tests: list[str]
    caller_paths: list[_SerializedCallerPath]


class SerializedTrackerState(TypedDict):
    """All process-local result state that the xdist controller must merge."""

    crossings: list[_SerializedCrossing]
    seen_ignore_patterns: list[str]
    used_ignore_patterns: list[str]


def serialize_tracker_state(
    *,
    crossings: Iterable[CrossingRecord],
    seen_ignore_patterns: Iterable[str],
    used_ignore_patterns: Iterable[str],
) -> SerializedTrackerState:
    """Encode tracker results using only xdist-serializable values."""
    return {
        "crossings": [
            {
                "execution_frame": _serialize_frame(crossing.execution_frame),
                "crossed_aggregates": list(crossing.crossed_aggregates),
                "involved_models": list(crossing.involved_models),
                "tests": sorted(crossing.tests),
                "caller_paths": [
                    {
                        "frames": [_serialize_frame(frame) for frame in path],
                        "tests": sorted(tests),
                    }
                    for path, tests in sorted(crossing.caller_paths.items())
                ],
            }
            for crossing in crossings
        ],
        "seen_ignore_patterns": sorted(seen_ignore_patterns),
        "used_ignore_patterns": sorted(used_ignore_patterns),
    }


def iter_crossing_updates(
    *, state: SerializedTrackerState
) -> Iterator[_CrossingUpdate]:
    """Decode crossing records into updates accepted by CrossingTracker."""
    for serialized in state["crossings"]:
        execution = _deserialize_frame(serialized["execution_frame"])
        crossing = (
            tuple(serialized["crossed_aggregates"]),
            tuple(serialized["involved_models"]),
        )
        tests = serialized["tests"]
        if not tests:
            yield (execution,), crossing, None
        for test in tests:
            yield (execution,), crossing, test

        for caller_path in serialized["caller_paths"]:
            frames = (
                execution,
                *(_deserialize_frame(frame) for frame in caller_path["frames"]),
            )
            path_tests = caller_path["tests"]
            if not path_tests:
                yield frames, crossing, None
            for test in path_tests:
                yield frames, crossing, test


def matched_ignore_patterns(
    *, state: SerializedTrackerState
) -> tuple[list[str], list[str]]:
    """Return seen and used ignore patterns carried by serialized state."""
    return state["seen_ignore_patterns"], state["used_ignore_patterns"]


def _serialize_frame(frame: ProjectStackFrame) -> _SerializedFrame:
    return {
        "file": frame.file,
        "line_number": frame.line_number,
        "function": frame.function,
    }


def _deserialize_frame(frame: _SerializedFrame) -> ProjectStackFrame:
    return ProjectStackFrame(
        file=frame["file"],
        line_number=frame["line_number"],
        function=frame["function"],
    )
