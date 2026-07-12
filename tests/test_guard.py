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
    customer = models.ForeignKey(
        Customer, related_name="orders", on_delete=models.CASCADE
    )

    class Meta:
        app_label = "contenttypes"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.CASCADE)

    class Meta:
        app_label = "contenttypes"


class Supplier(models.Model):
    class Meta:
        app_label = "contenttypes"


class Product(models.Model):
    supplier = models.ForeignKey(Supplier, null=True, on_delete=models.CASCADE)
    customers = models.ManyToManyField(Customer, related_name="products")

    class Meta:
        app_label = "contenttypes"


AGGREGATES = {
    "contenttypes.customer": "customer",
    "contenttypes.order": "order",
    "contenttypes.orderline": "order",
    "contenttypes.product": "order",
    "contenttypes.supplier": "catalog",
}


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(Customer)
        schema_editor.create_model(Order)
        schema_editor.create_model(OrderLine)
        schema_editor.create_model(Supplier)
        schema_editor.create_model(Product)
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
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_select_related_crossing_is_recorded(guard):
    # select_related emits an INNER JOIN in the SQL, which the parser reads.
    list(Order.objects.select_related("customer"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")
    assert guard.crossings[0].involved_models == (
        "contenttypes.Customer",
        "contenttypes.Order",
    )


def test_raw_sql_crossing_is_recorded(guard):
    # .raw() runs through the same cursor path, so its join is seen too.
    order, customer = Order._meta.db_table, Customer._meta.db_table
    sql = f"SELECT o.id FROM {order} o JOIN {customer} c ON o.customer_id = c.id"
    list(Order.objects.raw(sql))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_bare_cursor_crossing_is_recorded(guard):
    # A hand-written cursor.execute is intercepted by the same wrapper.
    order, customer = Order._meta.db_table, Customer._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT o.id FROM {order} o JOIN {customer} c ON o.customer_id = c.id"
        )
        cursor.fetchall()
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_subquery_crossing_is_recorded(guard):
    # A table reached only through a subquery still counts as a crossing.
    inner = Customer.objects.filter(name="Ann").values("id")
    list(Order.objects.filter(customer_id__in=inner))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_unparseable_data_query_is_skipped(guard):
    # An unreadable data query is skipped without error (see ROADMAP for surfacing it).
    guard._handle_query("SELECT * FROM", connection.vendor)
    assert guard.crossings == []


def test_trimmed_fk_lookup_is_not_recorded(guard):
    # Django trims the join (FK column holds the pk), so the SQL reads one table.
    list(Order.objects.filter(customer__pk=1))
    list(Order.objects.filter(customer__id__in=[1, 2]))
    assert guard.crossings == []


def test_within_aggregate_query_is_not_recorded(guard):
    list(Order.objects.all())  # single aggregate
    assert guard.crossings == []


def test_prefetch_related_crossing_is_recorded(guard):
    # prefetch loads the related rows with a second single-table query; the
    # crossing is read off the relation path prefetch walked, not the SQL.
    customer = Customer.objects.create(name="Bob")
    Order.objects.create(customer=customer)

    list(Order.objects.prefetch_related("customer"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")
    assert guard.crossings[0].involved_models == (
        "contenttypes.Customer",
        "contenttypes.Order",
    )


def test_reverse_prefetch_crossing_is_recorded(guard):
    # A crossing in either direction: customer -> its orders.
    customer = Customer.objects.create(name="Cid")
    Order.objects.create(customer=customer)

    list(Customer.objects.prefetch_related("orders"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_many_to_many_prefetch_crossing_is_recorded(guard):
    customer = Customer.objects.create(name="Mia")
    product = Product.objects.create()
    customer.products.add(product)

    list(Customer.objects.prefetch_related("products"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_prefetch_via_default_accessor_is_recorded(guard):
    # Product.supplier has no related_name, so the reverse side is reached by
    # its default accessor ``product_set`` -- resolved by accessor, not field.
    supplier = Supplier.objects.create()
    Product.objects.create(supplier=supplier)

    list(Supplier.objects.prefetch_related("product_set"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("catalog", "order")


def test_nested_prefetch_flags_the_crossing_hop(guard):
    # orders__lines walks two steps: Customer -> Order crosses (customer/order),
    # Order -> OrderLine stays inside the order aggregate and is not flagged.
    customer = Customer.objects.create(name="Ned")
    order = Order.objects.create(customer=customer)
    OrderLine.objects.create(order=order)

    list(Customer.objects.prefetch_related("orders__lines"))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_prefetch_object_crossing_is_recorded(guard):
    # A Prefetch(...) object carries the same relation path as a plain string.
    from django.db.models import Prefetch

    customer = Customer.objects.create(name="Ola")
    Order.objects.create(customer=customer)

    list(Order.objects.prefetch_related(Prefetch("customer")))
    assert len(guard.crossings) == 1
    assert guard.crossings[0].crossed_aggregates == ("customer", "order")


def test_prefetch_within_aggregate_is_not_recorded(guard):
    customer = Customer.objects.create(name="Eve")
    order = Order.objects.create(customer=customer)
    OrderLine.objects.create(order=order)

    list(Order.objects.prefetch_related("lines"))
    assert guard.crossings == []


def test_prefetch_not_recorded_after_uninstall_when_another_tool_wraps_on_top():
    # Invariant: after uninstall the guard must never record again. Here another
    # tool wraps prefetch on top of ours, so our uninstall can't restore the
    # original and leaves our wrapper reachable in the middle of the chain.
    import django.db.models.query as query_module

    pristine = query_module.prefetch_related_objects
    tracker = IgnoreTracker(patterns=[])
    guard = BoundaryGuard(
        aggregates_config=AGGREGATES, ignore_tracker=tracker, root=Path("/proj")
    )
    try:
        guard._install_prefetch_hook()

        # A second tool wraps prefetch on top of ours.
        our_wrapper = query_module.prefetch_related_objects

        def other_tool_wrapper(model_instances, *lookups):
            return our_wrapper(model_instances, *lookups)

        query_module.prefetch_related_objects = other_tool_wrapper

        # We uninstall while stacked underneath the other tool.
        guard._remove_prefetch_hook()

        # A crossing prefetch now flows other_tool -> our (leaked) wrapper.
        customer = Customer.objects.create(name="Zed")
        Order.objects.create(customer=customer)
        list(Order.objects.prefetch_related("customer"))

        assert guard.crossings == []
    finally:
        query_module.prefetch_related_objects = pristine


def test_uninstall_restores_original_when_topmost():
    # The common case: nobody stacked on us, so uninstall must put Django's own
    # prefetch_related_objects back exactly.
    import django.db.models.query as query_module

    pristine = query_module.prefetch_related_objects
    tracker = IgnoreTracker(patterns=[])
    guard = BoundaryGuard(
        aggregates_config=AGGREGATES, ignore_tracker=tracker, root=Path("/proj")
    )
    try:
        guard._install_prefetch_hook()
        assert query_module.prefetch_related_objects is not pristine
        guard._remove_prefetch_hook()
        assert query_module.prefetch_related_objects is pristine
    finally:
        query_module.prefetch_related_objects = pristine


def test_prefetch_not_recorded_after_other_tool_restores_us():
    # Harder ordering: after we uninstall (stacked), the other tool uninstalls
    # too and restores OUR wrapper to the top. It must stay inert.
    import django.db.models.query as query_module

    pristine = query_module.prefetch_related_objects
    tracker = IgnoreTracker(patterns=[])
    guard = BoundaryGuard(
        aggregates_config=AGGREGATES, ignore_tracker=tracker, root=Path("/proj")
    )
    try:
        guard._install_prefetch_hook()
        our_wrapper = query_module.prefetch_related_objects

        def other_tool_wrapper(model_instances, *lookups):
            return our_wrapper(model_instances, *lookups)

        query_module.prefetch_related_objects = other_tool_wrapper
        guard._remove_prefetch_hook()
        # The other tool uninstalls, restoring what it saved -- our wrapper.
        query_module.prefetch_related_objects = our_wrapper

        customer = Customer.objects.create(name="Res")
        Order.objects.create(customer=customer)
        list(Order.objects.prefetch_related("customer"))

        assert guard.crossings == []
    finally:
        query_module.prefetch_related_objects = pristine


def test_reinstall_after_stacked_uninstall_fires_once():
    # Re-installing must not double-fire: the leaked wrapper from the first
    # install keeps its own (disabled) _HookState, so only the fresh wrapper
    # runs the check. A single shared flag would let both fire.
    import django.db.models.query as query_module

    pristine = query_module.prefetch_related_objects
    tracker = IgnoreTracker(patterns=[])
    guard = BoundaryGuard(
        aggregates_config=AGGREGATES, ignore_tracker=tracker, root=Path("/proj")
    )
    calls = []
    real_handle = guard._handle_prefetch

    def counting_handle(**kwargs):
        calls.append(1)
        return real_handle(**kwargs)

    guard._handle_prefetch = counting_handle
    try:
        guard._install_prefetch_hook()
        leaked_wrapper = query_module.prefetch_related_objects

        def other_tool_wrapper(model_instances, *lookups):
            return leaked_wrapper(model_instances, *lookups)

        query_module.prefetch_related_objects = other_tool_wrapper
        guard._remove_prefetch_hook()  # leaked_wrapper now inert, still reachable

        guard._install_prefetch_hook()  # fresh wrapper on top

        customer = Customer.objects.create(name="Twice")
        Order.objects.create(customer=customer)
        list(Order.objects.prefetch_related("customer"))

        assert len(calls) == 1
    finally:
        query_module.prefetch_related_objects = pristine
