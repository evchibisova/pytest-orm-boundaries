"""Rendering of the grouped crossing report (no Django needed)."""

from pytest_orm_boundaries import report
from pytest_orm_boundaries.callstack import ProjectStackFrame
from pytest_orm_boundaries.crossings import CrossingRecord


class _FakeReporter:
    def __init__(self):
        self.lines: list[str] = []
        self.writes: list[tuple[str, dict]] = []

    def section(self, title, **kwargs):
        self.lines.append(title)

    def write_line(self, line, **kwargs):
        self.lines.append(line)
        self.writes.append((line, kwargs))


def _render(crossings, *, verbose=False):
    reporter = _FakeReporter()
    report.report_crossings(
        terminalreporter=reporter, crossings=crossings, verbose=verbose
    )
    return reporter.lines


def _frame(file, line, function):
    return ProjectStackFrame(file=file, line_number=line, function=function)


def _crossing(
    file="app/pay.py",
    line=42,
    tests=("t1",),
    function="<unknown>",
    caller_paths=None,
):
    return CrossingRecord(
        execution_frame=_frame(file, line, function),
        crossed_aggregates=("order", "payment"),
        involved_models=("order.Invoice", "payrolls.IncomePayment"),
        tests=set(tests),
        caller_paths=caller_paths or {},
    )


def test_report_shows_call_place_aggregates_models_and_tests():
    text = "\n".join(
        _render(
            [
                _crossing(
                    tests=("test_a", "test_b"),
                    function="Payments.report",
                )
            ]
        )
    )
    assert "boundary crossings" in text
    assert "[1] app/pay.py:42 in Payments.report" in text
    assert "order ↔ payment" in text
    assert "payrolls.IncomePayment" in text  # a joined model
    assert "test_a" in text and "test_b" in text


def test_compact_report_shows_only_the_immediate_caller():
    immediate = _frame("app/views.py", 20, "PaymentsView.get")
    outer = _frame("app/urls.py", 30, "dispatch")
    crossing = _crossing(caller_paths={(immediate, outer): {"t1"}})

    text = "\n".join(_render([crossing]))

    assert "called from: app/views.py:20 in PaymentsView.get" in text
    assert "app/urls.py" not in text


def test_verbose_report_shows_full_distinct_call_chains():
    first = (
        _frame("app/orders.py", 20, "delete_orders"),
        _frame("app/views.py", 30, "OrdersView.delete"),
    )
    second = (_frame("app/refunds.py", 40, "delete_refunds"),)
    crossing = _crossing(
        tests=("t1", "t2"),
        caller_paths={first: {"t1"}, second: {"t2"}},
    )

    text = "\n".join(_render([crossing], verbose=True))

    assert "call chains:" in text
    assert "app/orders.py:20 in delete_orders" in text
    assert "called from app/views.py:30 in OrdersView.delete" in text
    assert "app/refunds.py:40 in delete_refunds" in text


def test_report_counts_call_places_and_distinct_tests():
    crossings = [
        _crossing(file="app/a.py", tests=("shared", "only_a")),
        _crossing(file="app/b.py", tests=("shared", "only_b")),
    ]
    lines = _render(crossings)
    # 2 places, 3 distinct tests (shared counted once)
    assert any("2 place(s)" in line and "3 test(s)" in line for line in lines)


def test_report_separates_call_places_with_a_blank_line():
    lines = _render(
        [
            _crossing(file="app/a.py"),
            _crossing(file="app/b.py"),
        ]
    )
    second_file = lines.index("[2] app/b.py:42")
    assert lines[second_file - 1] == ""


def test_report_numbers_and_highlights_call_places():
    reporter = _FakeReporter()
    report.report_crossings(
        terminalreporter=reporter,
        crossings=[_crossing(file="app/a.py"), _crossing(file="app/b.py")],
    )

    headings = [
        (line, style) for line, style in reporter.writes if line.startswith("[")
    ]
    assert headings == [
        ("[1] app/a.py:42", {"yellow": True, "bold": True}),
        ("[2] app/b.py:42", {"yellow": True, "bold": True}),
    ]


def test_report_truncates_long_test_lists_unless_verbose():
    many = tuple(f"test_{i}" for i in range(50))
    assert any("+47 more" in line for line in _render([_crossing(tests=many)]))  # 50-3
    assert not any("more" in line for line in _render([_crossing(tests=many)], verbose=True))


def test_report_ends_with_loud_failed_verdict():
    assert any("FAILED" in line for line in _render([_crossing()]))


def test_clean_run_is_silent():
    assert _render([]) == []
