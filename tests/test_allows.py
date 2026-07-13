"""Per-file allows: config parsing and the AllowList matching."""

from textwrap import dedent

import pytest

from pytest_orm_boundaries.allows import AllowList
from pytest_orm_boundaries.config import BoundariesConfigError, load_config


def _write(tmp_path, text: str):
    path = tmp_path / "boundaries.toml"
    path.write_text(dedent(text))
    return path


def test_no_allow_section_is_empty(tmp_path):
    path = _write(tmp_path, '[aggregates.order]\nmodels = ["shop.Order"]\n')
    assert load_config(path=path).allowed_files == []


def test_loads_file_patterns_in_order(tmp_path):
    path = _write(
        tmp_path,
        """
        [allow]
        files = ["app/reports.py", "app/read_models/*"]
        """,
    )
    assert load_config(path=path).allowed_files == [
        "app/reports.py",
        "app/read_models/*",
    ]


def test_allow_must_be_a_section(tmp_path):
    path = _write(tmp_path, 'allow = "app/reports.py"\n')
    with pytest.raises(
        BoundariesConfigError,
        match=r"\[allow\] must be a section with a 'files' list",
    ):
        load_config(path=path)


def test_allow_files_not_a_list_raises(tmp_path):
    path = _write(tmp_path, '[allow]\nfiles = "app/reports.py"\n')
    with pytest.raises(BoundariesConfigError, match=r"\[allow\] files must be a list"):
        load_config(path=path)


def test_allow_files_non_string_entry_raises(tmp_path):
    path = _write(tmp_path, "[allow]\nfiles = [123]\n")
    with pytest.raises(BoundariesConfigError, match=r"\[allow\].*non-string"):
        load_config(path=path)


def test_has_allow_for_a_listed_file():
    allow_list = AllowList(patterns=["app/reports.py"])
    assert allow_list.has_allow_for(file_paths=["app/reports.py"]) is True


def test_no_allow_for_an_unlisted_file():
    allow_list = AllowList(patterns=["app/reports.py"])
    assert allow_list.has_allow_for(file_paths=["app/orders.py"]) is False


def test_has_allow_for_a_glob_match():
    allow_list = AllowList(patterns=["app/read_models/*"])
    assert allow_list.has_allow_for(file_paths=["app/read_models/sales.py"]) is True


def test_inactive_when_no_patterns():
    assert AllowList(patterns=[]).is_active is False
