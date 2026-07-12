"""Rendering of the grouped crossing report (no Django needed)."""

from pytest_orm_boundaries import report
from pytest_orm_boundaries.crossings import CrossingRecord


class _FakeReporter:
    def __init__(self):
        self.lines: list[str] = []

    def section(self, title, **kwargs):
        self.lines.append(title)

    def write_line(self, line, **kwargs):
        self.lines.append(line)


def _render(crossings, *, verbose=False):
    reporter = _FakeReporter()
    report.report_crossings(
        terminalreporter=reporter, crossings=crossings, verbose=verbose
    )
    return reporter.lines


def _crossing(file="app/pay.py", line=42, tests=("t1",)):
    return CrossingRecord(
        file=file,
        line_number=line,
        crossed_aggregates=("order", "payment"),
        involved_models=("order.Invoice", "payrolls.IncomePayment"),
        tests=set(tests),
    )


def test_report_shows_call_place_aggregates_models_and_tests():
    text = "\n".join(_render([_crossing(tests=("test_a", "test_b"))]))
    assert "boundary crossings" in text
    assert "app/pay.py:42" in text
    assert "order ↔ payment" in text
    assert "payrolls.IncomePayment" in text  # a joined model
    assert "test_a" in text and "test_b" in text


def test_report_counts_call_places_and_distinct_tests():
    crossings = [
        _crossing(file="app/a.py", tests=("shared", "only_a")),
        _crossing(file="app/b.py", tests=("shared", "only_b")),
    ]
    lines = _render(crossings)
    # 2 places, 3 distinct tests (shared counted once)
    assert any("2 place(s)" in line and "3 test(s)" in line for line in lines)


def test_report_truncates_long_test_lists_unless_verbose():
    many = tuple(f"test_{i}" for i in range(50))
    assert any("+45 more" in line for line in _render([_crossing(tests=many)]))  # 50-5
    assert not any("more" in line for line in _render([_crossing(tests=many)], verbose=True))


def test_report_ends_with_loud_failed_verdict():
    assert any("FAILED" in line for line in _render([_crossing()]))


def test_clean_run_is_silent():
    assert _render([]) == []
