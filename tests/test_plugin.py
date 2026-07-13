"""Tests for the pytest plugin wiring (options, config discovery)."""

from importlib.metadata import entry_points

import pytest

def test_registered_under_pytest11_entry_point():
    entrypoints = entry_points(group="pytest11")
    assert any(ep.value == "pytest_orm_boundaries.plugin" for ep in entrypoints)


def test_help_lists_config_option(pytester: pytest.Pytester):
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*--boundaries-config*"])


def test_inactive_without_config_file(pytester: pytest.Pytester):
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(
        ["*orm-boundaries: no config file, checks disabled*"]
    )


def test_warns_when_no_config_file(pytester: pytest.Pytester):
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, warnings=1)
    result.stdout.fnmatch_lines(["*boundaries.toml found*"])


def test_finds_default_config_in_rootdir(pytester: pytest.Pytester):
    pytester.path.joinpath("boundaries.toml").write_text("")
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*orm-boundaries: config *boundaries.toml*"])


def test_explicit_config_via_cli_option(pytester: pytest.Pytester):
    pytester.path.joinpath("custom.toml").write_text("")
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest("--boundaries-config", "custom.toml")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*orm-boundaries: config *custom.toml*"])


def test_explicit_config_via_ini(pytester: pytest.Pytester):
    pytester.path.joinpath("custom.toml").write_text("")
    pytester.makeini(
        """
        [pytest]
        boundaries_config = custom.toml
        """
    )
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*orm-boundaries: config *custom.toml*"])


def test_missing_explicit_config_is_usage_error(pytester: pytest.Pytester):
    result = pytester.runpytest("--boundaries-config", "missing.toml")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*config file not found*missing.toml*"])


def test_invalid_ignore_section_is_usage_error(pytester: pytest.Pytester):
    pytester.path.joinpath("boundaries.toml").write_text(
        '[aggregates.order]\nmodels = ["shop.Order"]\n'
        '[ignore]\nfiles = "oops.py"\n'
    )
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*orm-boundaries:*[[]ignore[]] files must be a list*"])


def test_invalid_config_is_usage_error(pytester: pytest.Pytester):
    pytester.path.joinpath("boundaries.toml").write_text(
        '[aggregates.order]\nmodels = ["shop.Order"]\n'
        '[aggregates.billing]\nmodels = ["shop.Order"]\n'
    )
    pytester.makepyfile("def test_ok(): pass")
    result = pytester.runpytest()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*orm-boundaries:*claimed by two aggregates*"])
