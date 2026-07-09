"""Integration test: the guard records boundary-crossing Django queries.

Django is configured in conftest; two models in different aggregates let us run
real queries through the installed guard.
"""

from pathlib import Path

import pytest

from pytest_orm_boundaries.guard import BoundaryGuard
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


@pytest.fixture
def guard():
    tracker = IgnoreTracker(patterns=[])
    guard = BoundaryGuard(
        aggregates_config=AGGREGATES, ignore_tracker=tracker, root=Path("/proj")
    )
    guard.install()
    yield guard
    guard.uninstall()


def test_crossing_query_is_recorded(guard):
    # Real join (non-key field) -> a genuine crossing, collected not raised.
    list(Order.objects.filter(customer__name="Ann"))
    assert len(guard.violations) == 1
    assert guard.violations[0].crossed_aggregates == ("customer", "order")


def test_select_related_crossing_is_recorded(guard):
    # select_related's join never reaches alias_map; it's read from klass_info.
    list(Order.objects.select_related("customer"))
    assert len(guard.violations) == 1
    assert guard.violations[0].crossed_aggregates == ("customer", "order")
    assert guard.violations[0].joined_models == (
        "contenttypes.Customer",
        "contenttypes.Order",
    )


def test_trimmed_fk_lookup_is_not_recorded(guard):
    # Django trims the join (FK column holds the pk), so the SQL reads one table.
    list(Order.objects.filter(customer__pk=1))
    list(Order.objects.filter(customer__id__in=[1, 2]))
    assert guard.violations == []


def test_within_aggregate_query_is_not_recorded(guard):
    list(Order.objects.all())  # single aggregate
    assert guard.violations == []


def test_records_group_by_call_place_and_accumulate_tests(guard):
    # _record_violation is the grouping unit: same (file, line, aggregates) -> one entry.
    crossing = (("order", "payment"), ("order.Invoice", "payment.Allocation"))
    guard.set_current_test("t1")
    guard._record_violation(call_place=("app/a.py", 10), crossing=crossing)
    guard.set_current_test("t2")
    guard._record_violation(call_place=("app/a.py", 10), crossing=crossing)
    guard._record_violation(call_place=("app/b.py", 5), crossing=crossing)

    # Sorted most-affecting first: a.py (2 tests) before b.py (1 test).
    violations = guard.violations
    assert [(v.file, v.line_number) for v in violations] == [
        ("app/a.py", 10),
        ("app/b.py", 5),
    ]
    assert violations[0].tests == {"t1", "t2"}
    assert violations[1].tests == {"t2"}
