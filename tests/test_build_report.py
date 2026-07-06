"""Rendering of the grouped violation report (no Django needed)."""

from pytest_orm_boundaries import build_report
from pytest_orm_boundaries.guard import ViolationRecord


class _FakeReporter:
    def __init__(self):
        self.lines: list[str] = []

    def section(self, title, **kwargs):
        self.lines.append(title)

    def write_line(self, line, **kwargs):
        self.lines.append(line)


def _render(violations, *, verbose=False):
    reporter = _FakeReporter()
    build_report.report_violations(
        terminalreporter=reporter, violations=violations, verbose=verbose
    )
    return reporter.lines


def _violation(file="app/pay.py", line=42, line_code="Order.objects.get(pk=1)", tests=("t1",)):
    return ViolationRecord(
        file=file,
        line_number=line,
        line_code=line_code,
        crossed="order, payment",
        tests=set(tests),
    )


def test_report_shows_call_place_code_crossing_and_tests():
    text = "\n".join(_render([_violation(tests=("test_a", "test_b"))]))
    assert "boundary violations" in text
    assert "app/pay.py:42" in text
    assert "Order.objects.get(pk=1)" in text  # the offending line of code
    assert "order, payment" in text
    assert "test_a" in text and "test_b" in text


def test_report_counts_call_places_and_distinct_tests():
    violations = [
        _violation(file="app/a.py", tests=("shared", "only_a")),
        _violation(file="app/b.py", tests=("shared", "only_b")),
    ]
    lines = _render(violations)
    # 2 places, 3 distinct tests (shared counted once)
    assert any("2 place(s)" in line and "3 test(s)" in line for line in lines)


def test_report_truncates_long_test_lists_unless_verbose():
    many = tuple(f"test_{i}" for i in range(50))
    assert any("+30 more" in line for line in _render([_violation(tests=many)]))  # 50-20
    assert not any("more" in line for line in _render([_violation(tests=many)], verbose=True))


def test_report_omits_line_code_when_unreadable():
    lines = _render([_violation(line_code="")])
    assert any("app/pay.py:42" in line for line in lines)
    assert not any(line == "    " for line in lines)  # no blank stand-in line


def test_report_ends_with_loud_failed_verdict():
    assert any("FAILED" in line for line in _render([_violation()]))


def test_clean_run_is_silent():
    assert _render([]) == []
