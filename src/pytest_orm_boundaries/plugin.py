"""Pytest plugin wiring: options, config discovery, activation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pytest_orm_boundaries import report
from pytest_orm_boundaries.config import (
    CONFIG_FILE_NAME,
    BoundariesConfigError,
    discover_config_path,
    load_config,
)
from pytest_orm_boundaries.allows import AllowList
from pytest_orm_boundaries.guard import BoundaryGuard
from pytest_orm_boundaries.ignores import IgnoreTracker

config_path_key = pytest.StashKey[Path | None]()
guard_key = pytest.StashKey["BoundaryGuard"]()
worker_output_key = "pytest_orm_boundaries"


class BoundariesConfigWarning(UserWarning):
    """Plugin is installed but won't run: no config file, or Django is absent."""


def _installed_guard(config: pytest.Config) -> BoundaryGuard | None:
    """The guard for this run, or None if no config or aggregates were found."""
    return config.stash.get(guard_key, None)


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


def _build_guard(*, rootpath: Path, config_path: Path) -> BoundaryGuard | None:
    """Build the guard from config, or None if no aggregates are declared."""
    config = load_config(path=config_path)
    if not config.aggregates_by_model:
        return None

    allow_list = AllowList(patterns=config.allowed_files)
    ignore_tracker = IgnoreTracker(patterns=config.ignored_files)
    return BoundaryGuard(
        aggregates_config=config.aggregates_by_model,
        allow_list=allow_list,
        ignore_tracker=ignore_tracker,
        root=rootpath,
    )


def pytest_configure(config: pytest.Config) -> None:
    """Resolve config and install the guard, stashing both for later hooks:
    the config path for the report header, the guard for teardown and reporting.
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

        if importlib.util.find_spec("django") is None:
            warning = BoundariesConfigWarning(
                f"{CONFIG_FILE_NAME} found but Django is not installed, no checks "
                "will run (install pytest-orm-boundaries[django])"
            )
            config.issue_config_time_warning(warning, stacklevel=2)
            return

        guard = _build_guard(rootpath=config.rootpath, config_path=config_path)
        if guard is not None:
            guard.install()
            config.stash[guard_key] = guard
    except BoundariesConfigError as exc:
        raise pytest.UsageError(f"orm-boundaries: {exc}") from exc


def pytest_unconfigure(config: pytest.Config) -> None:
    guard = _installed_guard(config)
    if guard is not None:
        guard.uninstall()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    """Tell the guard which test is running so a crossing can name it."""
    guard = _installed_guard(item.config)
    if guard is not None:
        guard.set_current_test(item.nodeid)
    try:
        return (yield)
    finally:
        if guard is not None:
            guard.set_current_test(None)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """A clean-but-violating run must still fail the run (via the exit code)."""
    guard = _installed_guard(session.config)
    if guard is None:
        return
    if hasattr(session.config, "workerinput"):
        session.config.workeroutput[worker_output_key] = guard.serialize_state()
        return
    if guard.crossings and exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error) -> None:
    """Merge one xdist worker's results into the controller's guard."""
    guard = _installed_guard(node.config)
    worker_output = getattr(node, "workeroutput", {})
    state = worker_output.get(worker_output_key)
    if guard is not None and state is not None:
        guard.merge_state(state)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    guard = _installed_guard(config)
    if guard is None:
        return
    report.report_crossings(
        terminalreporter=terminalreporter,
        crossings=guard.crossings,
        verbose=config.getoption("verbose", 0) > 0,
    )
    stale = guard.find_stale_patterns()
    report.report_stale_ignores(terminalreporter=terminalreporter, stale=stale)


def pytest_report_header(config: pytest.Config) -> str:
    config_path = config.stash.get(config_path_key, None)
    return report.render_header(config_path=config_path)
