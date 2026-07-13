"""Locating, reading, and validating ``boundaries.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILE_NAME = "boundaries.toml"


class BoundariesConfigError(Exception):
    """Raised when the config file is malformed or semantically invalid."""


@dataclass(frozen=True)
class BoundariesConfig:
    """Parsed and validated content of a ``boundaries.toml``."""

    aggregates_by_model: dict[str, str]  # {"app.model" lower-cased: aggregate_name}
    ignored_files: list[str]  # globs for known debt, tracked for staleness
    allowed_files: list[str]  # globs for intentional crossings, never stale


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


def load_config(*, path: Path) -> BoundariesConfig:
    data = _read_config(path=path)
    return BoundariesConfig(
        aggregates_by_model=_parse_aggregates(data=data, path=path),
        ignored_files=_parse_file_globs(data=data, path=path, section_name="ignore"),
        allowed_files=_parse_file_globs(data=data, path=path, section_name="allow"),
    )


def _read_config(*, path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise BoundariesConfigError(f"{path}: invalid TOML ({exc})") from exc


def _parse_aggregates(*, data: dict[str, Any], path: Path) -> dict[str, str]:
    """Build a {model_label: aggregate_name} map from the ``[aggregates]`` table.

    Model labels are lower-cased ("app_label.modelname") for case-insensitive
    matching.
    """
    aggregate_definitions = data.get("aggregates", {})
    if not isinstance(aggregate_definitions, dict):
        raise BoundariesConfigError(
            f"{path}: define aggregates as named sections, for example "
            "[aggregates.order] with models = [...]"
        )

    aggregates_by_model: dict[str, str] = {}
    for aggregate, definition in aggregate_definitions.items():
        if not isinstance(definition, dict):
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' must define models in its own "
                "section: "
                f"[aggregates.{aggregate}] with models = [...]"
            )

        unknown_fields = set(definition) - {"models"}
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' has unknown field(s): {fields}"
            )

        if "models" not in definition:
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' is missing required 'models'"
            )
        members = definition["models"]
        if not isinstance(members, list):
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' models must be a list"
            )
        if not members:
            raise BoundariesConfigError(
                f"{path}: aggregate '{aggregate}' models must not be empty"
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


def _parse_file_globs(
    *, data: dict[str, Any], path: Path, section_name: str
) -> list[str]:
    """Read ``[allow]`` and ``[ignore] files`` into a list of glob patterns."""
    section_data = data.get(section_name, {})
    if not isinstance(section_data, dict):
        raise BoundariesConfigError(
            f"{path}: [{section_name}] must be a section with a 'files' list"
        )

    files = section_data.get("files", [])
    if not isinstance(files, list):
        raise BoundariesConfigError(
            f"{path}: [{section_name}] files must be a list of glob patterns"
        )

    patterns: list[str] = []
    for entry in files:
        if not isinstance(entry, str):
            raise BoundariesConfigError(
                f"{path}: [{section_name}] files has a non-string entry: {entry!r}"
            )
        patterns.append(entry)
    return patterns
