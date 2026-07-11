"""Render orm-boundaries results to the pytest terminal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_orm_boundaries.config import CONFIG_FILE_NAME

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from pytest_orm_boundaries.guard import ViolationRecord

MAX_TESTS_SHOWN = 5


def report_violations(
    *,
    terminalreporter: pytest.TerminalReporter,
    violations: list[ViolationRecord],
    verbose: bool = False,
) -> None:
    """Print one grouped entry per offending call place: which aggregates the
    query crossed, the models it joined, and which tests reached it.
    """
    if not violations:
        return

    affected = len({test for violation in violations for test in violation.tests})
    terminalreporter.section(
        "orm-boundaries: boundary violations", red=True, bold=True
    )
    terminalreporter.write_line(
        f"{len(violations)} place(s) in your code crossed aggregate boundaries, "
        f"affecting {affected} test(s):",
        red=True,
    )
    for violation in violations:
        _write_violation(
            terminalreporter=terminalreporter, violation=violation, verbose=verbose
        )
    terminalreporter.write_line("")
    terminalreporter.write_line(
        f"orm-boundaries: FAILED - {len(violations)} boundary violation(s), "
        "run exits non-zero.",
        red=True,
        bold=True,
    )


def _write_violation(
    *,
    terminalreporter: pytest.TerminalReporter,
    violation: ViolationRecord,
    verbose: bool,
) -> None:
    terminalreporter.write_line("")
    terminalreporter.write_line(f"{violation.file}:{violation.line_number}", bold=True)
    aggregates = " ↔ ".join(violation.crossed_aggregates)
    terminalreporter.write_line(
        f"    crossed aggregates: {aggregates}", yellow=True, bold=True
    )
    models = ", ".join(violation.joined_models)
    terminalreporter.write_line(f"    models: {models}")

    tests = sorted(violation.tests)
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


def report_stale_ignores(
    *, terminalreporter: pytest.TerminalReporter, stale: list[str]
) -> None:
    if not stale:
        return
    terminalreporter.section("orm-boundaries: stale ignores", yellow=True, bold=True)
    terminalreporter.write_line(
        "These [ignore] entries no longer suppress any boundary violation - "
        f"their files are clean now. Remove them from {CONFIG_FILE_NAME}:",
        yellow=True,
    )
    for pattern in stale:
        terminalreporter.write_line(f"  - {pattern}", yellow=True)


def render_header(*, config_path: Path | None) -> str:
    if config_path is None:
        return "orm-boundaries: no config file, checks disabled"
    return f"orm-boundaries: config {config_path}"
