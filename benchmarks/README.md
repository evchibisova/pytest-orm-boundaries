# Benchmarks

Run the query-overhead benchmark from the repository root:

```bash
uv run python benchmarks/benchmark_query_overhead.py
```

The benchmark compares the same query workload with and without the boundary
guard. It covers cached ORM queries, `allow`, `ignore`, actual crossings, and
SQL parse-cache misses. The stack-sensitive cases include a simulated deep
pytest stack.

Results are intentionally informational rather than a CI pass/fail check:
absolute timings vary by machine and load. Compare the median results from two
branches on the same machine when evaluating a performance change. Use
`--help` to adjust the query count, repetitions, or simulated stack depth.

For the raw in-memory SQLite scenarios, focus on `added/query`. Their baseline
is only a few microseconds, so percentages make small absolute costs look large.
