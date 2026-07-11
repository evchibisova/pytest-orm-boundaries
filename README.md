# pytest-orm-boundaries

> 💡 **Even if you control your imports — boundaries still can leak through the ORM**

A `pytest-orm-boundaries` is a pytest plugin that reports ORM queries crossing your DDD aggregate boundaries.

Currently works with Django ORM.

In domain-driven design, an aggregate is a consistency boundary: code in one
aggregate should not reach into the internals of another. Django's `__` relation
lookups make it easy to cross those boundaries silently:

```python
# Purchase and Client belong to different aggregates — this query couples them.
Purchase.objects.get(client__name="John")
```

`pytest-orm-boundaries` watches the SQL your test suite executes and reports the
queries that step outside their aggregate — whether through `__` lookups,
`select_related`, subqueries, or hand-written `.raw()` SQL.

## Install

```bash
pip install pytest-orm-boundaries
```

pytest picks the plugin up automatically.

## Configure

Declare your aggregates in `boundaries.toml` at the project root (or point at
the file with `--boundaries-config` / the `boundaries_config` ini option):

```toml
[aggregates]
client   = ["bookshop.Client"]
book     = ["bookshop.Book"]
purchase = ["bookshop.Purchase", "bookshop.PurchaseLine"]
```

Models are written as `app_label.Model`. Models not listed in any aggregate are
not checked. Without a config file the plugin emits a warning and runs no checks.

## What it catches

The plugin works from the SQL your suite actually executes, so it flags any
single statement that reads tables from two different aggregates - however the
query was written. Each example below joins the `purchase` and `client` aggregates:

- `__` relation lookups:

  ```python
  Purchase.objects.get(client__name="John")
  ```

- `select_related`

  ```python
  Purchase.objects.select_related("client")
  ```

- Subqueries - a table reached through a subquery still counts:

  ```python
  berlin_clients = Client.objects.filter(city="Berlin").values("id")
  Purchase.objects.filter(client_id__in=berlin_clients)
  ```

- Hand-written `.raw()` SQL:

  ```python
  Purchase.objects.raw(
      "SELECT p.id FROM bookshop_purchase p "
      "JOIN bookshop_client c ON p.client_id = c.id"
  )
  ```

- Bare `cursor.execute()` - the same join reached through a raw cursor.

Queries that don't actually join across the boundary are **not** flagged — for
example a foreign-key lookup by id, which Django resolves without a join:

```python
Purchase.objects.filter(client_id=42)     # reads one table
Purchase.objects.filter(client__pk=42)    # Django trims the join
```

## The report

At the end of the run, the plugin prints one grouped entry per offending place:

```
===================== orm-boundaries: boundary violations ======================
1 place(s) in your code crossed aggregate boundaries, affecting 1 test(s):

bookshop/reports.py:13
    crossed aggregates: client ↔ purchase
    models: bookshop.Client, bookshop.Purchase
    1 test(s) affected:
      test_purchases.py::test_list_purchases_with_client

orm-boundaries: FAILED - 1 boundary violation(s), run exits non-zero.
```

Each entry names the aggregates the query crossed and the models it joined.
Places are ordered by how many tests they affect. Pass `-v` to see every affected test
(otherwise the list is capped at 5 per place).

## Ignoring files

Add exceptions so that known offenders keep passing while you fix them one file at a time:

```toml
[ignore]
files = [
    "app/billing.py",
    "app/legacy/*",
]
```

Each entry is a glob ([`fnmatch`](https://docs.python.org/3/library/fnmatch.html),
resolved relative to pytest's root directory and matched against either:

- the file that issues the query, or
- the test file.

If an ignored file runs queries through the whole suite without ever crossing a
boundary, the plugin says so at the end:

```
======================= orm-boundaries: stale ignores ========================
These [ignore] entries no longer suppress any boundary violation - their files are clean now.
Remove them from boundaries.toml:
  - app/billing.py
```

## Known gaps

- `prefetch_related` loads doesn't detected in current version.

## Status

Alpha - testing basic version.
