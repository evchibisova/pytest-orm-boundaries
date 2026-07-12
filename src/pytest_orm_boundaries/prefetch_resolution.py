"""Turn a ``prefetch_related`` lookup into the model pairs it steps between.

A prefetch loads the other aggregate with a separate single-table query, so the
SQL alone never looks like a boundary crossing. Django's prefetch,
though, is handed the exact relation path it walks; so the guard can apply the aggregate rule to
each step without inspecting any SQL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import Model


def resolve_prefetch_step_models(
    *, source_model: type[Model],
    lookups: Iterable[object],
) -> list[tuple[str, str]]:
    """Return one ``(owner_model_label, target_model_label)`` pair per relation step.

    A nested lookup such as ``lines__product`` yields a pair for each step.
    """
    from django.db.models.constants import LOOKUP_SEP

    step_model_pairs: list[tuple[str, str]] = []
    for lookup in lookups:
        path = _extract_lookup_path(lookup=lookup)
        if path is None:
            continue
        owner = source_model
        for lookup_step in path.split(LOOKUP_SEP):
            target = _resolve_target_lookup_step_model(model=owner, lookup_step=lookup_step)
            if target is None:
                break
            step_models = (owner._meta.label, target._meta.label)
            step_model_pairs.append(step_models)
            owner = target
    return step_model_pairs


def _extract_lookup_path(*, lookup: object) -> str | None:
    if isinstance(lookup, str):
        return lookup
    return getattr(lookup, "prefetch_through", None)


def _resolve_target_lookup_step_model(
    *,
    model: type[Model],
    lookup_step: str,
) -> type[Model] | None:
    from django.core.exceptions import FieldDoesNotExist

    try:
        field = model._meta.get_field(lookup_step)
    except FieldDoesNotExist:
        field = None
    if field is not None and field.is_relation:
        return field.related_model
    # A reverse relation without ``related_name`` is reached by its accessor
    # (``order_set``), a name get_field doesn't know; match it by accessor.
    for candidate in model._meta.get_fields():
        if not candidate.is_relation:
            continue
        read_accessor_name = getattr(candidate, "get_accessor_name", None)
        if read_accessor_name is not None and read_accessor_name() == lookup_step:
            return candidate.related_model
    return None
