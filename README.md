# pytest-orm-boundaries

A pytest plugin that fails your tests when ORM queries cross your DDD aggregate boundaries.

Currently works with Django ORM.

In domain-driven design, an aggregate is a consistency boundary: code in one
aggregate should not reach into the internals of another. Django's `__` relation
lookups make it easy to cross those boundaries silently:

```python
# Payment and Order belong to different aggregates — this query couples them.
Purchase.objects.get(client__name="John")
```

`pytest-orm-boundaries` watches the queries your test suite executes and
reports the ones that step outside their aggregate, including `__`, subqueries and other.

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

## Status

Alpha - testing basic version.
