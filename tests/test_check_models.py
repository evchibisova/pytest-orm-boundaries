"""Unit tests for _check_models: detecting queries that cross aggregates.

A tiny stand-in replaces a Django model, so these need neither Django nor a
configured app registry.
"""

import pytest

from pytest_orm_boundaries.check_boundaries import BoundaryViolation, _check_models


class _FakeModel:
    """Stand-in for a Django model: only ``_meta.label``/``label_lower`` are read."""

    def __init__(self, label: str) -> None:
        self._meta = type(
            "_Meta", (), {"label": label, "label_lower": label.lower()}
        )()


AGGREGATES = {
    "shop.order": "order",
    "shop.orderline": "order",
    "shop.client": "client",
}


def test_no_violation_within_one_aggregate():
    models = [_FakeModel("shop.Order"), _FakeModel("shop.OrderLine")]
    _check_models(models=models, aggregates_config=AGGREGATES)  # does not raise


def test_no_violation_for_single_model():
    _check_models(models=[_FakeModel("shop.Client")], aggregates_config=AGGREGATES)


def test_unmapped_models_are_ignored():
    # other.Thing is in no aggregate, so this stays a single-aggregate query.
    models = [_FakeModel("shop.Order"), _FakeModel("other.Thing")]
    _check_models(models=models, aggregates_config=AGGREGATES)  # does not raise


def test_violation_across_two_aggregates():
    models = [_FakeModel("shop.Order"), _FakeModel("shop.Client")]
    with pytest.raises(BoundaryViolation) as exc_info:
        _check_models(models=models, aggregates_config=AGGREGATES)
    # Both aggregate names and both joined model labels are reported, sorted.
    message = str(exc_info.value)
    assert "client, order" in message
    assert "shop.Client, shop.Order" in message
