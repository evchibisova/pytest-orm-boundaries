"""Render orm-boundaries results to the pytest terminal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_orm_boundaries.callstack import ProjectStackFrame
from pytest_orm_boundaries.config import CONFIG_FILE_NAME

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from pytest_orm_boundaries.crossings import CrossingRecord

MAX_TESTS_SHOWN = 3
MAX_CALLERS_SHOWN = 3


def report_crossings(
    *,
    terminalreporter: pytest.TerminalReporter,
    crossings: list[CrossingRecord],
    verbose: bool = False,
) -> None:
    """Print one grouped entry per offending call place: which aggregates the
    query crossed, the models involved, and which tests reached it.
    """
    if not crossings:
        return

    affected = len({test for crossing in crossings for test in crossing.tests})
    terminalreporter.section(
        "orm-boundaries: boundary crossings", red=True, bold=True
    )
    terminalreporter.write_line(
        f"{len(crossings)} place(s) in your code crossed aggregate boundaries, "
        f"affecting {affected} test(s):",
        red=True,
    )
    for index, crossing in enumerate(crossings):
        if index:
            terminalreporter.write_line("")
        _write_crossing(
            terminalreporter=terminalreporter,
            crossing=crossing,
            number=index + 1,
            verbose=verbose,
        )
    terminalreporter.write_line("")
    terminalreporter.write_line(
        f"orm-boundaries: FAILED - {len(crossings)} boundary crossing(s), "
        "run exits non-zero.",
        red=True,
        bold=True,
    )


def _write_crossing(
    *,
    terminalreporter: pytest.TerminalReporter,
    crossing: CrossingRecord,
    number: int,
    verbose: bool,
) -> None:
    terminalreporter.write_line(
        f"[{number}] {_format_frame(crossing.execution_frame)}",
        yellow=True,
        bold=True,
    )
    aggregates = " ↔ ".join(crossing.crossed_aggregates)
    terminalreporter.write_line(
        f"    crossed aggregates: {aggregates}", yellow=True, bold=True
    )
    models = ", ".join(crossing.involved_models)
    terminalreporter.write_line(f"    models: {models}")
    _write_callers(
        terminalreporter=terminalreporter, crossing=crossing, verbose=verbose
    )

    tests = sorted(crossing.tests)
    if not tests:
        terminalreporter.write_line("    tests affected: (none captured)", light=True)
        return

    shown = tests if verbose else tests[:MAX_TESTS_SHOWN]
    terminalreporter.write_line(f"    {len(tests)} test(s) affected:", light=True)
    for nodeid in shown:
        terminalreporter.write_line(f"      {nodeid}", light=True)
    hidden = len(tests) - len(shown)
    if hidden:
        terminalreporter.write_line(
            f"      ... +{hidden} more (-v to list all)", light=True
        )


def _write_callers(
    *,
    terminalreporter: pytest.TerminalReporter,
    crossing: CrossingRecord,
    verbose: bool,
) -> None:
    paths = sorted(crossing.caller_paths)
    if not paths:
        return

    if not verbose:
        immediate_callers = sorted({path[0] for path in paths})
        if len(immediate_callers) == 1:
            terminalreporter.write_line(
                f"    called from: {_format_frame(immediate_callers[0])}",
                light=True,
            )
            return

        terminalreporter.write_line("    called from:", light=True)
        for frame in immediate_callers[:MAX_CALLERS_SHOWN]:
            terminalreporter.write_line(f"      {_format_frame(frame)}", light=True)
        hidden = len(immediate_callers) - MAX_CALLERS_SHOWN
        if hidden > 0:
            terminalreporter.write_line(
                f"      ... +{hidden} more (-v to list full call chains)",
                light=True,
            )
        return

    title = "call chain:" if len(paths) == 1 else "call chains:"
    terminalreporter.write_line(f"    {title}", light=True)
    for path in paths:
        terminalreporter.write_line(f"      {_format_frame(path[0])}", light=True)
        for frame in path[1:]:
            terminalreporter.write_line(
                f"        called from {_format_frame(frame)}", light=True
            )


def _format_frame(frame: ProjectStackFrame) -> str:
    location = f"{frame.file}:{frame.line_number}"
    if frame.function == "<unknown>":
        return location
    return f"{location} in {frame.function}"


def report_stale_ignores(
    *, terminalreporter: pytest.TerminalReporter, stale: list[str]
) -> None:
    if not stale:
        return
    terminalreporter.section("orm-boundaries: stale ignores", yellow=True, bold=True)
    terminalreporter.write_line(
        "These [ignore] entries matched files that ran without crossing a "
        f"boundary. Remove them from {CONFIG_FILE_NAME}:",
        yellow=True,
    )
    for pattern in stale:
        terminalreporter.write_line(f"  - {pattern}", yellow=True)


def render_header(*, config_path: Path | None) -> str:
    if config_path is None:
        return "orm-boundaries: no config file, checks disabled"
    return f"orm-boundaries: config {config_path}"
