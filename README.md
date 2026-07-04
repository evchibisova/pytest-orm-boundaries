# pytest-orm-boundaries

> 💡 **Even if you control your imports — boundaries still can leak through the ORM**

A `pytest-orm-boundaries` is a pytest plugin that fails your tests when ORM queries cross your DDD aggregate boundaries.

Currently works with Django ORM.

In domain-driven design, an aggregate is a consistency boundary: code in one
aggregate should not reach into the internals of another. Django's `__` relation
lookups make it easy to cross those boundaries silently:

```python
# Purchase and Client belong to different aggregates — this query couples them.
Purchase.objects.get(client__name="John")
```

`pytest-orm-boundaries` watches the queries your test suite executes and
reports the ones that step outside their aggregate, whether through `__`
lookups, subqueries, or other joins.

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

## Status

Alpha - testing basic version.
