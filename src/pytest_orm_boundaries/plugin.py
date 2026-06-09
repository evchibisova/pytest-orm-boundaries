"""Pytest plugin wiring: options, config discovery, activation."""

from __future__ import annotations

from pathlib import Path

import pytest

from .check_boundaries import (
    BoundariesConfigError,
    install_guard,
    load_aggregates_from_config,
    uninstall_guard,
)

CONFIG_FILE_NAME = "boundaries.toml"

config_path_key = pytest.StashKey[Path | None]()
original_execute_sql_key = pytest.StashKey[object]()


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
            f"{CONFIG_FILE_NAME} in the pytest root directory; if no config "
            "file is found, boundary checks are disabled."
        ),
    )
    parser.addini(
        "boundaries_config",
        help="Same as --boundaries-config.",
        default="",
    )


def _discover_config_path(*, config: pytest.Config) -> Path | None:
    explicit = config.getoption("boundaries_config") or config.getini(
        "boundaries_config"
    )
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = config.rootpath / path
        if not path.is_file():
            raise pytest.UsageError(
                f"orm-boundaries: config file not found: {path}"
            )
        return path
    default = config.rootpath / CONFIG_FILE_NAME
    return default if default.is_file() else None


def pytest_configure(config: pytest.Config) -> None:
    path = _discover_config_path(config=config)
    config.stash[config_path_key] = path
    if path is None:
        config.issue_config_time_warning(
            BoundariesConfigWarning(
                f"no {CONFIG_FILE_NAME} found in the pytest root directory; "
                "orm-boundaries is inactive, so no boundary checks will run."
            ),
            stacklevel=2,
        )
        return
    try:
        aggregates_by_model = load_aggregates_from_config(path=path)
    except BoundariesConfigError as exc:
        raise pytest.UsageError(f"orm-boundaries: {exc}") from exc
    if not aggregates_by_model:
        # Config present but defines no aggregates, so skip patching entirely.
        return
    config.stash[original_execute_sql_key] = install_guard(
        aggregates_config=aggregates_by_model
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    original = config.stash.get(original_execute_sql_key, None)
    if original is not None:
        uninstall_guard(original=original)


def pytest_report_header(config: pytest.Config) -> str:
    path = config.stash.get(config_path_key, None)
    if path is None:
        return "orm-boundaries: no config file, checks disabled"
    return f"orm-boundaries: config {path}"
