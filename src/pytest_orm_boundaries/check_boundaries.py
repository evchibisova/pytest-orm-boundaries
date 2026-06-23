"""Aggregate-boundary checking: parse the config, watch queries, fail on crossings.

Django is imported lazily, inside the functions that need it (and under
TYPE_CHECKING for annotations), so importing this module never requires Django
to be installed.
"""

from __future__ import annotations

import functools
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db.models.sql.query import Query


class BoundaryViolation(Exception):
    """Raised when a query joins models from more than one aggregate."""


class BoundariesConfigError(Exception):
    """Raised when the config file is malformed or semantically invalid."""


def load_aggregates_from_config(*, path: Path) -> dict[str, str]:
    """Parse the config into a {model_label: aggregate_name} map.

    Model labels are lower-cased ("app_label.modelname") for case-insensitive
    matching.
    """
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise BoundariesConfigError(f"{path}: invalid TOML ({exc})") from exc

    aggregates_by_model: dict[str, str] = {}
    for aggregate, members in data.get("aggregates", {}).items():
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


def _check_models(
    *,
    models: Iterable[type[Model]],
    aggregates_config: dict[str, str],
) -> None:
    
    aggregate_by_model_label = {
        model._meta.label: aggregate
        for model in models
        if (aggregate := aggregates_config.get(model._meta.label_lower)) is not None
    }
    aggregates = set(aggregate_by_model_label.values())
    if len(aggregates) <= 1:
        return

    crossed = ", ".join(sorted(aggregates))
    joined = ", ".join(sorted(aggregate_by_model_label.keys()))
    raise BoundaryViolation(
        f"orm-boundaries: query crosses aggregate boundaries "
        f"({crossed}); joined models: {joined}"
    )


@functools.cache
def _table_to_model() -> dict[str, type[Model]]:
    """Map db_table -> model class for every installed model."""
    from django.apps import apps

    return {model._meta.db_table: model for model in apps.get_models()}


def _get_models_from_query(*, query: Query) -> list[type[Model]]:
    table_to_model = _table_to_model()
    return [
        table_to_model[table.table_name]
        for table in query.alias_map.values()
        if table.table_name in table_to_model
    ]


def install_guard(*, aggregates_config: dict[str, str]) -> Callable[..., Any]:
    """Wrap SQLCompiler.execute_sql to check every executed query.

    Returns the original method so the caller can restore it later.
    """
    from django.db.models.sql.compiler import SQLCompiler

    original = SQLCompiler.execute_sql

    def patched_execute_sql(self, *args, **kwargs):
        query_models = _get_models_from_query(query=self.query)
        _check_models(
            models=query_models,
            aggregates_config=aggregates_config,
        )
        return original(self, *args, **kwargs)

    SQLCompiler.execute_sql = patched_execute_sql
    return original


def uninstall_guard(*, original: Callable[..., Any]) -> None:
    """Restore the original SQLCompiler.execute_sql."""
    from django.db.models.sql.compiler import SQLCompiler

    SQLCompiler.execute_sql = original
