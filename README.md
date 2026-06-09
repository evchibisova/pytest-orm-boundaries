# django-orm-boundaries

A standalone linter that enforces the **DDD aggregate boundaries you define** in
your Django ORM.

In Domain-Driven Design, an aggregate is a consistency boundary: code in one
aggregate should not reach into the internals of another. Django's `__` relation
lookups make it easy to cross those boundaries silently:

```python
# Payment and Order belong to different aggregates — this query couples them.
Payment.objects.get(invoice__order__id=1)
```

`django-orm-boundaries` parses your code (no runtime required), follows the
relation lookups you declared, and reports when a queryset rooted in one
aggregate steps into another.

## Install

```bash
pip install django-orm-boundaries
```

## Run

```bash
orm-boundaries .                       # check the current tree
orm-boundaries src/ tests/             # check specific paths
orm-boundaries --config orm-boundaries.toml src/
```
