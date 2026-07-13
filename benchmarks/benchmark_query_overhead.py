"""Measure the per-query overhead of the Django boundary guard."""

from __future__ import annotations

import argparse
import gc
import platform
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import django
from django.conf import settings


GuardMode = Literal["plain", "allow", "ignore"]
QueryRunner = Callable[[int], None]


@dataclass(frozen=True)
class Scenario:
    name: str
    queries: int
    runner: QueryRunner
    guard_mode: GuardMode = "plain"
    deep_stack: bool = False
    warm_cache: bool = True
    clear_sql_cache: bool = False


@dataclass(frozen=True)
class Result:
    name: str
    queries: int
    without_guard: float
    with_guard: float

    @property
    def added_per_query_us(self) -> float:
        return (self.with_guard - self.without_guard) / self.queries * 1_000_000

    @property
    def overhead_percent(self) -> float:
        return (self.with_guard - self.without_guard) / self.without_guard * 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=int, default=2_000)
    parser.add_argument("--unique-queries", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--stack-depth", type=int, default=40)
    return parser.parse_args()


def configure_django() -> None:
    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=["django.contrib.contenttypes"],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        )
    django.setup()


def build_runtime_functions(*, root: Path):
    """Give benchmark frames stable project and third-party-looking paths."""
    runtime_namespace: dict[str, object] = {}
    exec(
        compile(
            """
def cursor_same(connection, sql, queries):
    with connection.cursor() as cursor:
        for _ in range(queries):
            cursor.execute(sql)
            cursor.fetchone()

def cursor_unique(connection, sql, queries):
    with connection.cursor() as cursor:
        for index in range(queries):
            cursor.execute(f"{sql} /* benchmark-{index} */")
            cursor.fetchone()

def orm_same(model, queries):
    for _ in range(queries):
        list(model.objects.filter(id=-1).values_list("id", flat=True))
""",
            str(root / "benchmarks" / "_runtime.py"),
            "exec",
        ),
        runtime_namespace,
    )

    stack_namespace: dict[str, object] = {}
    exec(
        compile(
            """
def call_with_stack(action, depth):
    if depth:
        return call_with_stack(action, depth - 1)
    return action()
""",
            str(
                root
                / ".venv"
                / "lib"
                / "python"
                / "site-packages"
                / "pytest"
                / "_benchmark_stack.py"
            ),
            "exec",
        ),
        stack_namespace,
    )
    return runtime_namespace, stack_namespace["call_with_stack"]


def main() -> None:
    args = parse_args()
    if args.queries <= 0 or args.unique_queries <= 0 or args.repeats <= 0:
        raise SystemExit("query counts and repeats must be positive")
    if args.stack_depth < 0:
        raise SystemExit("stack depth must not be negative")

    configure_django()

    from django.db import connection, models

    from pytest_orm_boundaries.allows import AllowList
    from pytest_orm_boundaries.guard import BoundaryGuard
    from pytest_orm_boundaries.ignores import IgnoreTracker
    from pytest_orm_boundaries.model_resolution import map_tables_to_models
    from pytest_orm_boundaries.sql_parsing import extract_table_names

    class BenchmarkA(models.Model):
        class Meta:
            app_label = "contenttypes"

    class BenchmarkB(models.Model):
        class Meta:
            app_label = "contenttypes"

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(BenchmarkA)
        schema_editor.create_model(BenchmarkB)

    map_tables_to_models.cache_clear()
    root = Path(__file__).resolve().parents[1]
    runtime, call_with_stack = build_runtime_functions(root=root)
    cursor_same = runtime["cursor_same"]
    cursor_unique = runtime["cursor_unique"]
    orm_same = runtime["orm_same"]

    single_sql = f"SELECT id FROM {BenchmarkA._meta.db_table} WHERE id = -1"
    crossing_sql = (
        f"SELECT a.id FROM {BenchmarkA._meta.db_table} a "
        f"JOIN {BenchmarkB._meta.db_table} b ON a.id = b.id WHERE a.id = -1"
    )
    aggregates = {
        BenchmarkA._meta.label_lower: "alpha",
        BenchmarkB._meta.label_lower: "beta",
    }

    def new_guard(mode: GuardMode) -> BoundaryGuard:
        return BoundaryGuard(
            aggregates_config=aggregates,
            allow_list=AllowList(
                patterns=["benchmarks/_runtime.py"] if mode == "allow" else []
            ),
            ignore_tracker=IgnoreTracker(
                patterns=["benchmarks/_runtime.py"] if mode == "ignore" else []
            ),
            root=root,
        )

    def raw_runner(sql: str) -> QueryRunner:
        return lambda queries: cursor_same(connection, sql, queries)

    scenarios = [
        Scenario(
            name="cached Django ORM SELECT",
            queries=args.queries,
            runner=lambda queries: orm_same(BenchmarkA, queries),
        ),
        Scenario(
            name="clean SELECT with allow",
            queries=args.queries,
            runner=raw_runner(single_sql),
            guard_mode="allow",
            deep_stack=True,
        ),
        Scenario(
            name="clean SELECT with ignore",
            queries=args.queries,
            runner=raw_runner(single_sql),
            guard_mode="ignore",
            deep_stack=True,
        ),
        Scenario(
            name="crossing SELECT",
            queries=args.queries,
            runner=raw_runner(crossing_sql),
            deep_stack=True,
        ),
        Scenario(
            name="unique SELECTs (parse misses)",
            queries=args.unique_queries,
            runner=lambda queries: cursor_unique(connection, single_sql, queries),
            warm_cache=False,
            clear_sql_cache=True,
        ),
    ]

    def execute(scenario: Scenario, queries: int) -> None:
        action = lambda: scenario.runner(queries)
        if scenario.deep_stack:
            call_with_stack(action, args.stack_depth)
        else:
            action()

    def measure_once(scenario: Scenario, *, active: bool) -> float:
        guard = new_guard(scenario.guard_mode) if active else None
        if guard is not None:
            guard.install()
        try:
            if active and scenario.clear_sql_cache:
                extract_table_names.cache_clear()
            if scenario.warm_cache:
                execute(scenario, 1)
            gc.collect()
            gc.disable()
            started = time.perf_counter()
            execute(scenario, scenario.queries)
            return time.perf_counter() - started
        finally:
            gc.enable()
            if guard is not None:
                guard.uninstall()

    results: list[Result] = []
    for scenario in scenarios:
        samples = {False: [], True: []}
        for repeat in range(args.repeats):
            order = (False, True) if repeat % 2 == 0 else (True, False)
            for active in order:
                samples[active].append(measure_once(scenario, active=active))
        results.append(
            Result(
                name=scenario.name,
                queries=scenario.queries,
                without_guard=statistics.median(samples[False]),
                with_guard=statistics.median(samples[True]),
            )
        )

    print(
        f"Python {platform.python_version()}, Django {django.get_version()}, "
        f"SQLite in-memory; median of {args.repeats} runs"
    )
    print("Raw SQLite baselines are tiny; compare added/query across branches.")
    print(
        f"{'scenario':36} {'off (ms)':>10} {'on (ms)':>10} "
        f"{'overhead':>10} {'added/query':>14}"
    )
    for result in results:
        print(
            f"{result.name:36} "
            f"{result.without_guard * 1_000:10.2f} "
            f"{result.with_guard * 1_000:10.2f} "
            f"{result.overhead_percent:9.1f}% "
            f"{result.added_per_query_us:11.2f} us"
        )


if __name__ == "__main__":
    main()
