# Roadmap

Plan to improve. Not commitments - priorities can shift.

## A readable violations report

A run prints hundreds of near-identical failure lines, and it's hard to tell what
actually broke. Add a report that groups everything by the line of code that
crossed a boundary - showing that line and the tests it affected - so you can see
and fix the real problem at a glance.

## Trustworthy "stale ignore" hints

The hint that suggests removing an ignore entry need fix: on a partial test run it can tell you to delete one you still need.

## Catch crossings it currently misses

The plugin inspects a query before Django finishes building the final SQL, so
joins added at that last step slip through: for example, data pulled in from
another aggregate via `select_related`. We'd need to check the query once it is
fully built, so these genuine crossings aren't missed silently.

## Warn on unknown models in the config

Mistype a model name in `boundaries.toml` and that model is silently left
unchecked - you think it's protected when it isn't. Warn loudly about names that
don't match a real model.

## Later

### Configurable project root

Ignore paths are resolved relative to where pytest thinks the project root is,
which can shift between setups. Let the config pin the root so ignores keep
working.
