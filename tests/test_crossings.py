"""Unit tests for the aggregate rule and the crossing tracker (no Django needed)."""

from pathlib import Path

from pytest_orm_boundaries.allows import AllowList
from pytest_orm_boundaries.crossings import CrossingTracker
from pytest_orm_boundaries.ignores import IgnoreTracker

AGGREGATES = {
    "shop.order": "order",
    "shop.orderline": "order",
    "billing.invoice": "billing",
}


def _make_tracker(*, patterns=(), allow_patterns=()):
    return CrossingTracker(
        aggregates_config=AGGREGATES,
        allow_list=AllowList(patterns=allow_patterns),
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


def _fix_frames(monkeypatch, file: str):
    """Pin the call place check() sees, so allow/ignore matching is testable
    without a real project stack."""
    from pytest_orm_boundaries import crossings

    monkeypatch.setattr(
        crossings, "find_frames_inside_project", lambda *, root: [(file, 7)]
    )


CROSSING = [["shop.Order", "billing.Invoice"]]


def test_allow_suppresses_a_crossing(monkeypatch):
    _fix_frames(monkeypatch, "app/reports.py")
    tracker = _make_tracker(allow_patterns=["app/reports.py"])
    tracker.check(label_sets=CROSSING)
    assert tracker.crossings == []


def test_ignore_suppresses_and_is_not_stale_when_used(monkeypatch):
    _fix_frames(monkeypatch, "app/billing.py")
    tracker = _make_tracker(patterns=["app/billing.py"])
    tracker.check(label_sets=CROSSING)
    assert tracker.crossings == []
    assert tracker.find_stale_patterns() == []


def test_allow_wins_over_ignore_and_leaves_the_ignore_stale(monkeypatch):
    # A file in both sections: allow suppresses the crossing, and because the
    # ignore is never marked used it surfaces as stale - redundant, remove it.
    _fix_frames(monkeypatch, "app/reports.py")
    tracker = _make_tracker(
        patterns=["app/reports.py"], allow_patterns=["app/reports.py"]
    )
    tracker.check(label_sets=CROSSING)
    assert tracker.crossings == []
    assert tracker.find_stale_patterns() == ["app/reports.py"]


def test_serialized_states_merge_crossings_from_multiple_workers():
    crossing = (("billing", "order"), ("billing.Invoice", "shop.Order"))
    worker_one = _make_tracker()
    worker_one.add_record(
        call_place=("app/report.py", 10), crossing=crossing, test="test_one"
    )
    worker_two = _make_tracker()
    worker_two.add_record(
        call_place=("app/report.py", 10), crossing=crossing, test="test_two"
    )

    controller = _make_tracker()
    controller.merge_state(worker_one.serialize_state())
    controller.merge_state(worker_two.serialize_state())

    assert len(controller.crossings) == 1
    assert controller.crossings[0].tests == {"test_one", "test_two"}


def test_serialized_states_union_ignore_activity_across_workers(monkeypatch):
    patterns = ["app/*.py", "app/stale.py"]

    clean_worker = _make_tracker(patterns=patterns)
    _fix_frames(monkeypatch, "app/clean.py")
    clean_worker.check(label_sets=[["shop.Order"]])

    crossing_worker = _make_tracker(patterns=patterns)
    _fix_frames(monkeypatch, "app/crossing.py")
    crossing_worker.check(label_sets=CROSSING)

    stale_worker = _make_tracker(patterns=patterns)
    _fix_frames(monkeypatch, "app/stale.py")
    stale_worker.check(label_sets=[["shop.Order"]])

    controller = _make_tracker(patterns=patterns)
    for worker in (clean_worker, crossing_worker, stale_worker):
        controller.merge_state(worker.serialize_state())

    assert controller.crossings == []
    assert controller.find_stale_patterns() == ["app/stale.py"]
