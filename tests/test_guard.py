"""Integration test: the guard actually fails a boundary-crossing Django query.

Django is configured in conftest; two models in different aggregates let us run
a real query through the installed guard.
"""

from pathlib import Path

import pytest

from pytest_orm_boundaries.guard import BoundaryGuard, BoundaryViolation
from pytest_orm_boundaries.ignores import IgnoreTracker

pytest.importorskip("django")

from django.db import connection, models  # noqa: E402


class Customer(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "contenttypes"


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    class Meta:
        app_label = "contenttypes"


AGGREGATES = {"contenttypes.customer": "customer", "contenttypes.order": "order"}


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(Customer)
        schema_editor.create_model(Order)
    yield


@pytest.fixture(autouse=True)
def _installed_guard():
    tracker = IgnoreTracker(patterns=[], root=Path("/proj"))
    guard = BoundaryGuard(aggregates_config=AGGREGATES, ignore_tracker=tracker)
    guard.install()
    yield
    guard.restore_original_runner()


def test_crossing_query_raises():
    with pytest.raises(BoundaryViolation, match="customer, order"):
        list(Order.objects.filter(customer__name="Ann"))


def test_trimmed_fk_lookup_across_boundary_does_not_raise():
    # Django trims the join (FK column holds the pk), so the SQL reads one table.
    list(Order.objects.filter(customer__pk=1))
    list(Order.objects.filter(customer__id__in=[1, 2]))


def test_within_aggregate_query_passes():
    list(Order.objects.all())  # single aggregate -> runs without a violation
