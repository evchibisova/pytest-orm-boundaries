# pytest-orm-boundaries

💡 **Even if you control your imports, boundaries can still leak through the ORM.**

`pytest-orm-boundaries` is a pytest plugin that reports ORM queries crossing your DDD aggregate boundaries.

Currently works with Django ORM, SQLAlchemy is in roadmap.

In domain-driven design, an aggregate is a consistency boundary: code in one
aggregate should not reach into the internals of another. Django's `__` relation
lookups make it easy to cross those boundaries silently:

```python
# Purchase and Client belong to different aggregates — this query couples them.
Purchase.objects.get(client__name="John")
```

`pytest-orm-boundaries` watches the ORM activity exercised by your test suite
and reports access that crosses a configured boundary - through `__` lookups,
`select_related`, `prefetch_related`, subqueries, or hand-written `.raw()` SQL.

## Install

Install the plugin with Django support:

```bash
pip install "pytest-orm-boundaries[django]"
```

pytest discovers the plugin automatically.

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

The plugin flags executed ORM access that spans more than one configured group.
In the DDD example below, each crossing couples the `purchase` and `client`
aggregates:

- `__` relation lookups:

  ```python
  Purchase.objects.get(client__name="John")
  ```

- `select_related`:

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

- `prefetch_related`:

  ```python
  Purchase.objects.prefetch_related("client")
  ```

Queries that don't actually join across the boundary are **not** flagged - for
example a foreign-key lookup by id, which Django resolves without a join:

```python
Purchase.objects.filter(client_id=42)     # reads one table
Purchase.objects.filter(client__pk=42)    # Django trims the join
```

## The report

At the end of the run, the plugin prints one grouped entry per offending place:

```
====================== orm-boundaries: boundary crossings ======================
1 place(s) in your code crossed aggregate boundaries, affecting 1 test(s):

bookshop/reports.py:13
    crossed aggregates: client ↔ purchase
    models: bookshop.Client, bookshop.Purchase
    1 test(s) affected:
      test_purchases.py::test_list_purchases_with_client

orm-boundaries: FAILED - 1 boundary crossing(s), run exits non-zero.
```

Each entry names the aggregates the query crossed and the models it joined.
Places are ordered by how many tests they affect. Pass `-v` to see every affected test
(otherwise the list is capped at 5 per place).

## Allow and ignore

CQRS read models may cross boundaries intentionally, also existing application code may contain crossings you want to fix over time. [allow] and [ignore] let you tell the plugin which is which:

- `[allow]` - the crossing is **intentional**. Use it for code that is meant to
  span aggregates, such as CQRS read models or cross-aggregate reports. An
  allowed crossing is suppressed and never reported.
- `[ignore]` - the crossing is **known debt** you plan to fix. It is suppressed
  for now, and the plugin reminds you when an entry is no longer needed.

```toml
[allow]
files = [
    "app/reports/sales_summary.py",
]

[ignore]
files = [
    "app/billing.py",
    "app/legacy/*",
]
```

Each entry is a glob ([`fnmatch`](https://docs.python.org/3/library/fnmatch.html)),
resolved relative to pytest's root directory and matched against either:

- the file that issues the query, or
- the test file.

An `[ignore]` whose file runs through the whole suite without ever crossing a
boundary is stale — it is clean now, so the plugin lists it for removal:

```
======================= orm-boundaries: stale ignores ========================
These [ignore] entries no longer suppress any boundary crossing - their files are clean now.
Remove them from boundaries.toml:
  - app/billing.py
```

`[allow]` entries are never reported this way. If a file sits in both sections,
the allow wins and its `[ignore]` entry shows up as stale to remove.

## A note on Django internals

Catching `prefetch_related` relies on Django internals that come with no stability
promise, so new Django releases may require compatibility updates.

## Known gaps (on the project roadmap)

- lazy attribute access (e.g. `purchase.client`);
- related-manager reads/writes (`client.purchases.all()`, `client.purchases.create(...)`);
- a direct query on another aggregate's model, e.g. `Client.objects.get(...)` written inside purchase code.

## Status

Alpha - testing basic version.
