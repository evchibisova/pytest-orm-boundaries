"""Resolve Django model labels for the table names a query reads."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import Model


def resolve_labels(table_names: Iterable[str]) -> list[str]:
    """Resolve model labels for the given table names, dropping unmapped names."""
    table_to_model = map_tables_to_models()
    return [
        table_to_model[table]._meta.label
        for table in table_names
        if table in table_to_model
    ]


@functools.cache
def map_tables_to_models() -> dict[str, type[Model]]:
    """Map db_table -> model class for every installed model."""
    from django.apps import apps

    return {model._meta.db_table: model for model in apps.get_models()}
