"""Unit tests for the aggregate rule and the crossing tracker (no Django needed)."""

from pathlib import Path

from pytest_orm_boundaries.crossings import CrossingTracker
from pytest_orm_boundaries.ignores import IgnoreTracker

AGGREGATES = {
    "shop.order": "order",
    "shop.orderline": "order",
    "billing.invoice": "billing",
}


def _make_tracker(*, patterns=()):
    return CrossingTracker(
        aggregates_config=AGGREGATES,
        ignore_tracker=IgnoreTracker(patterns=patterns),
        root=Path("/proj"),
    )


def test_labels_in_one_aggregate_are_not_a_crossing():
    tracker = _make_tracker()
    assert tracker.find_crossing(labels=["shop.Order", "shop.OrderLine"]) is None


def test_labels_across_aggregates_are_a_crossing():
    tracker = _make_tracker()
    crossing = tracker.find_crossing(labels=["shop.Order", "billing.Invoice"])
    assert crossing == (("billing", "order"), ("billing.Invoice", "shop.Order"))


def test_unconfigured_labels_leave_a_single_aggregate():
    tracker = _make_tracker()
    # catalog.Book is in no aggregate -> only one aggregate present -> clean.
    assert tracker.find_crossing(labels=["shop.Order", "catalog.Book"]) is None


def test_records_group_by_call_place_and_accumulate_tests():
    tracker = _make_tracker()
    crossing = (("order", "billing"), ("shop.Order", "billing.Invoice"))
    tracker.add_record(call_place=("app/a.py", 10), crossing=crossing, test="t1")
    tracker.add_record(call_place=("app/a.py", 10), crossing=crossing, test="t2")
    tracker.add_record(call_place=("app/b.py", 5), crossing=crossing, test="t2")

    # Sorted most-affecting first: a.py (2 tests) before b.py (1 test).
    crossings = tracker.crossings
    assert [(v.file, v.line_number) for v in crossings] == [
        ("app/a.py", 10),
        ("app/b.py", 5),
    ]
    assert crossings[0].tests == {"t1", "t2"}
    assert crossings[1].tests == {"t2"}


def test_check_records_only_the_crossing_sets():
    # check() runs the rule over each set; only the crossing one is recorded,
    # attributed to the current test.
    tracker = _make_tracker()
    tracker.set_current_test("t1")
    tracker.check(
        label_sets=[
            ["shop.Order", "billing.Invoice"],  # crosses order/billing
            ["shop.Order", "shop.OrderLine"],  # clean, one aggregate
        ]
    )
    crossings = tracker.crossings
    assert len(crossings) == 1
    assert crossings[0].crossed_aggregates == ("billing", "order")
    assert crossings[0].tests == {"t1"}
