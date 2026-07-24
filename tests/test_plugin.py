"""Tests for the pytest plugin wiring (options, config discovery)."""

from importlib.metadata import entry_points

import pytest


def test_registered_under_pytest11_entry_point():
    entrypoints = entry_points(group="pytest11")
    assert any(ep.value == "pytest_orm_boundaries.plugin" for ep in entrypoints)


def test_help_lists_plugin_options(pytester: pytest.Pytester):
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(
        ["*--boundaries-config*", "*--boundaries-stale-ignores*"]
    )


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


def _configure_active_plugin(pytester: pytest.Pytester, *, ignores=()) -> None:
    ignore_section = ""
    if ignores:
        patterns = ", ".join(f'"{pattern}"' for pattern in ignores)
        ignore_section = f"\n[ignore]\nfiles = [{patterns}]\n"
    pytester.path.joinpath("boundaries.toml").write_text(
        '[aggregates.order]\nmodels = ["shop.Order"]\n'
        '[aggregates.customer]\nmodels = ["shop.Customer"]\n'
        f"{ignore_section}"
    )
    shop = pytester.path.joinpath("shop")
    shop.mkdir()
    shop.joinpath("__init__.py").write_text("")
    shop.joinpath("models.py").write_text(
        """
from contextlib import contextmanager

from django.db import connection, models


class Customer(models.Model):
    name = models.CharField(max_length=100)


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)


@contextmanager
def tables():
    with connection.schema_editor() as editor:
        editor.create_model(Customer)
        editor.create_model(Order)
    try:
        yield
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(Order)
            editor.delete_model(Customer)
        """
    )
    pytester.makeconftest(
        """
        from django.conf import settings

        def pytest_configure():
            if not settings.configured:
                settings.configure(
                    DATABASES={
                        "default": {
                            "ENGINE": "django.db.backends.sqlite3",
                            "NAME": ":memory:",
                        }
                    },
                    INSTALLED_APPS=["shop"],
                )
                import django
                django.setup()
        """
    )


def test_xdist_reports_worker_crossings_and_fails_run(pytester: pytest.Pytester):
    _configure_active_plugin(pytester)
    pytester.makepyfile(
        test_crossing="""
        from shop.models import Customer, Order, tables

        def test_crossing():
            with tables():
                list(Order.objects.filter(customer__name="Ann"))
        """
    )

    serial = pytester.runpytest_subprocess()
    distributed = pytester.runpytest_subprocess("-n", "2")

    for result in (serial, distributed):
        result.assert_outcomes(passed=1)
        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(
            [
                "*orm-boundaries: boundary crossings*",
                "*test_crossing.py:*",
                "*orm-boundaries: FAILED - 1 boundary crossing(s)*",
            ]
        )


def test_shared_execution_site_reports_distinct_callers_in_serial_and_xdist(
    pytester: pytest.Pytester,
):
    _configure_active_plugin(pytester)
    pytester.makepyfile(
        shared_query="""
        def evaluate(queryset):
            return list(queryset)
        """,
        crossing_callers="""
        from shared_query import evaluate
        from shop.models import Order

        def from_orders():
            return evaluate(Order.objects.filter(customer__name="Ann"))

        def from_billing():
            return evaluate(Order.objects.filter(customer__name="Bea"))
        """,
        test_orders="""
        from crossing_callers import from_orders
        from shop.models import tables

        def test_orders():
            with tables():
                from_orders()
        """,
        test_billing="""
        from crossing_callers import from_billing
        from shop.models import tables

        def test_billing():
            with tables():
                from_billing()
        """,
    )

    serial = pytester.runpytest_subprocess()
    distributed = pytester.runpytest_subprocess("-n", "2", "--dist", "loadfile")

    for result in (serial, distributed):
        result.assert_outcomes(passed=2)
        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.stdout.fnmatch_lines(
            [
                "*1 place(s)*affecting 2 test(s)*",
                "*shared_query.py:* in evaluate*",
                "*called from:*",
                "*crossing_callers.py:* in from_orders*",
                "*crossing_callers.py:* in from_billing*",
                "*orm-boundaries: FAILED - 1 boundary crossing(s)*",
            ]
        )


def test_stale_ignores_are_opt_in_and_union_activity_from_all_xdist_workers(
    pytester: pytest.Pytester,
):
    shared_pattern = "test_shared_*.py"
    stale_pattern = "test_stale.py"
    _configure_active_plugin(
        pytester, ignores=(shared_pattern, stale_pattern)
    )
    pytester.makepyfile(
        test_shared_clean="""
        from shop.models import Order, tables

        def test_clean():
            with tables():
                list(Order.objects.all())
        """,
        test_shared_crossing="""
        from shop.models import Order, tables

        def test_crossing():
            with tables():
                list(Order.objects.filter(customer__name="Ann"))
        """,
        test_stale="""
        from shop.models import Order, tables

        def test_stale():
            with tables():
                list(Order.objects.all())
        """,
    )

    default = pytester.runpytest_subprocess()
    default.assert_outcomes(passed=3)
    assert default.ret == pytest.ExitCode.OK
    assert "orm-boundaries: stale ignores" not in default.stdout.str()

    serial = pytester.runpytest_subprocess("--boundaries-stale-ignores")
    distributed = pytester.runpytest_subprocess(
        "-n", "2", "--dist", "loadfile", "--boundaries-stale-ignores"
    )

    for result in (serial, distributed):
        result.assert_outcomes(passed=3)
        assert result.ret == pytest.ExitCode.OK
        stale_report = result.stdout.str().split(
            "orm-boundaries: stale ignores", maxsplit=1
        )[1]
        assert stale_pattern in stale_report
        assert shared_pattern not in stale_report
