"""Pytest plugin wiring: options, config discovery, activation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pytest_orm_boundaries import build_report
from pytest_orm_boundaries.guard import build_guard
from pytest_orm_boundaries.read_config import (
    CONFIG_FILE_NAME,
    BoundariesConfigError,
    discover_config_path,
)

if TYPE_CHECKING:
    from pytest_orm_boundaries.guard import BoundaryGuard

config_path_key = pytest.StashKey[Path | None]()
guard_key = pytest.StashKey["BoundaryGuard | None"]()


class BoundariesConfigWarning(UserWarning):
    """Plugin is installed but no config file was found."""


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("orm-boundaries")
    group.addoption(
        "--boundaries-config",
        dest="boundaries_config",
        metavar="PATH",
        default=None,
        help=(
            "Path to the boundaries TOML config. Defaults to "
            f"{CONFIG_FILE_NAME} in the pytest root directory; if no "
            "config file is found, boundary checks are disabled."
        ),
    )
    parser.addini(
        "boundaries_config",
        help="Same as --boundaries-config.",
        default="",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Resolve the config and install the guard, stashing what other hooks need:

    - ``config_path_key`` -- to show where the config came from in the report.
    - ``guard_key`` -- to restore the patched query method on teardown and to
      report stale ignores at the end of the run.
    """
    explicit_config = config.getoption("boundaries_config") or config.getini("boundaries_config")
    try:
        config_path = discover_config_path(
            explicit=explicit_config, rootpath=config.rootpath
        )
        config.stash[config_path_key] = config_path
        if config_path is None:
            warning = BoundariesConfigWarning(f"No {CONFIG_FILE_NAME} found, no checks will run")
            config.issue_config_time_warning(warning, stacklevel=2)
            return

        guard = build_guard(rootpath=config.rootpath, config_path=config_path)
        if guard is not None:
            guard.install()
            config.stash[guard_key] = guard
    except BoundariesConfigError as exc:
        raise pytest.UsageError(f"orm-boundaries: {exc}") from exc


def pytest_unconfigure(config: pytest.Config) -> None:
    guard = config.stash.get(guard_key, None)
    if guard is not None:
        guard.restore_original_runner()


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    guard = config.stash.get(guard_key, None)
    if guard is not None:
        stale = guard.find_stale_patterns()
        build_report.report_stale_ignores(
            terminalreporter=terminalreporter, stale=stale
        )


def pytest_report_header(config: pytest.Config) -> str:
    config_path = config.stash.get(config_path_key, None)
    return build_report.build_report_header(config_path=config_path)
