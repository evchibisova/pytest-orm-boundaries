"""Terminal output: the run header and the stale-ignore notice."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_orm_boundaries.read_config import CONFIG_FILE_NAME


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


def build_report_header(*, config_path: Path | None) -> str:
    if config_path is None:
        return "orm-boundaries: no config file, checks disabled"
    return f"orm-boundaries: config {config_path}"
