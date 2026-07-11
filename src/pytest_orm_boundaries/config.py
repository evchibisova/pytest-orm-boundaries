"""Locating, reading, and validating ``boundaries.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_FILE_NAME = "boundaries.toml"


class BoundariesConfigError(Exception):
    """Raised when the config file is malformed or semantically invalid."""


def discover_config_path(*, explicit: str | None, rootpath: Path) -> Path | None:
    """Resolve the config path.

    Fall back to the rootdir default and return None if it is absent.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = rootpath / path
        if not path.is_file():
            raise BoundariesConfigError(f"config file not found: {path}")
        return path
    default = rootpath / CONFIG_FILE_NAME
    return default if default.is_file() else None


def _read_config(*, path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise BoundariesConfigError(f"{path}: invalid TOML ({exc})") from exc


def load_aggregates_from_config(*, path: Path) -> dict[str, str]:
    """Parse the config into a {model_label: aggregate_name} map.

    Model labels are lower-cased ("app_label.modelname") for case-insensitive
    matching.
    """
    config = _read_config(path=path)

    aggregates_by_model: dict[str, str] = {}
    for aggregate, members in config.get("aggregates", {}).items():
        if isinstance(members, dict):
            members = members.get("models", [])
        if not isinstance(members, list):
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' must be a list of model labels"
            )
        for label in members:
            if not isinstance(label, str):
                raise BoundariesConfigError(
                    f"{path}: aggregate '{aggregate}' has a non-string member: {label!r}"
                )
            owner = aggregates_by_model.setdefault(label.lower(), aggregate)
            if owner != aggregate:
                raise BoundariesConfigError(
                    f"{path}: model '{label}' claimed by two aggregates: "
                    f"'{owner}' and '{aggregate}'"
                )
    return aggregates_by_model


def load_ignored_files_from_config(*, path: Path) -> list[str]:
    """Parse ``[ignore] files`` into a list of glob patterns."""
    data = _read_config(path=path)

    ignore = data.get("ignore", {})
    if not isinstance(ignore, dict):
        raise BoundariesConfigError(f"{path}: [ignore] must be a table")

    files = ignore.get("files", [])
    if not isinstance(files, list):
        raise BoundariesConfigError(
            f"{path}: [ignore] files must be a list of glob patterns"
        )

    patterns: list[str] = []
    for entry in files:
        if not isinstance(entry, str):
            raise BoundariesConfigError(
                f"{path}: [ignore] files has a non-string entry: {entry!r}"
            )
        patterns.append(entry)
    return patterns
