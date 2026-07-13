"""Per-file ignores: config parsing and the IgnoreTracker book-keeping."""

from textwrap import dedent

import pytest

from pytest_orm_boundaries.config import BoundariesConfigError, load_config
from pytest_orm_boundaries.ignores import IgnoreTracker


def _tracker(patterns):
    return IgnoreTracker(patterns=patterns)


def _write(tmp_path, text: str):
    path = tmp_path / "boundaries.toml"
    path.write_text(dedent(text))
    return path


def test_no_ignore_section_is_empty(tmp_path):
    path = _write(tmp_path, '[aggregates.order]\nmodels = ["shop.Order"]\n')
    assert load_config(path=path).ignored_files == []


def test_loads_file_patterns_in_order(tmp_path):
    path = _write(
        tmp_path,
        """
        [ignore]
        files = ["tests/test_a.py", "tests/legacy/*"]
        """,
    )
    assert load_config(path=path).ignored_files == [
        "tests/test_a.py",
        "tests/legacy/*",
    ]


def test_ignore_must_be_a_section(tmp_path):
    path = _write(tmp_path, 'ignore = "tests/test_a.py"\n')
    with pytest.raises(
        BoundariesConfigError,
        match=r"\[ignore\] must be a section with a 'files' list",
    ):
        load_config(path=path)


def test_ignore_files_not_a_list_raises(tmp_path):
    path = _write(tmp_path, '[ignore]\nfiles = "tests/test_a.py"\n')
    with pytest.raises(BoundariesConfigError, match="must be a list"):
        load_config(path=path)


def test_ignore_files_non_string_entry_raises(tmp_path):
    path = _write(tmp_path, "[ignore]\nfiles = [123]\n")
    with pytest.raises(BoundariesConfigError, match="non-string entry"):
        load_config(path=path)


def test_has_ignore_for_a_listed_file():
    tracker = _tracker(["app/billing.py"])
    assert tracker.has_ignore_for(file_paths=["app/billing.py"]) is True


def test_no_ignore_for_an_unlisted_file():
    tracker = _tracker(["app/billing.py"])
    assert tracker.has_ignore_for(file_paths=["app/orders.py"]) is False


def test_has_ignore_for_a_glob_match():
    tracker = _tracker(["app/legacy/*"])
    assert tracker.has_ignore_for(file_paths=["app/legacy/reports.py"]) is True


def test_inactive_when_no_patterns():
    assert _tracker([]).is_active is False


def test_stale_when_file_ran_without_a_crossing():
    tracker = _tracker(["app/billing.py"])
    tracker.mark_seen(file_paths=["app/billing.py"])  # ran a query, but stayed clean
    assert tracker.find_stale_patterns() == ["app/billing.py"]


def test_not_stale_when_the_ignore_was_used():
    tracker = _tracker(["app/billing.py"])
    tracker.mark_seen(file_paths=["app/billing.py"])
    tracker.mark_used(file_paths=["app/billing.py"])
    assert tracker.find_stale_patterns() == []


def test_not_stale_when_the_file_never_ran():
    # A partial run (the file issued no query) must not flag the ignore.
    assert _tracker(["app/never.py"]).find_stale_patterns() == []


def test_glob_kept_alive_if_any_match_violates():
    tracker = _tracker(["app/legacy/*"])
    tracker.mark_seen(file_paths=["app/legacy/clean.py"])
    tracker.mark_used(file_paths=["app/legacy/dirty.py"])
    assert tracker.find_stale_patterns() == []


class _FakeReporter:
    def __init__(self):
        self.lines: list[str] = []

    def section(self, title, **kwargs):
        self.lines.append(title)

    def write_line(self, line, **kwargs):
        self.lines.append(line)


def _summary_lines(tracker):
    from pytest_orm_boundaries import report

    reporter = _FakeReporter()
    stale = tracker.find_stale_patterns()
    report.report_stale_ignores(terminalreporter=reporter, stale=stale)
    return reporter.lines


def test_summary_lists_stale_ignores():
    tracker = _tracker(["app/clean.py"])
    tracker.mark_seen(file_paths=["app/clean.py"])  # ran clean -> stale
    lines = _summary_lines(tracker)
    assert any("stale ignores" in line for line in lines)
    assert any("matched files that ran without crossing" in line for line in lines)
    assert any("app/clean.py" in line for line in lines)


def test_summary_silent_when_nothing_stale():
    assert _summary_lines(_tracker(["app/clean.py"])) == []
