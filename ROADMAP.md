# Roadmap

Plan to improve. Not commitments - priorities can shift.

## Match ignores to the file that issues the query

An ignore matches if its file appears anywhere in the call chain, not just where
the query runs - so it can silence a crossing that only passes through, and can
make a stale ignore look live. Match ignores (and the stale check) to the file
that issues the query.

## Warn on unknown models in the config

A mistyped model name in `boundaries.toml` is silently left unchecked - you think
it's protected when it isn't. On startup, warn about names that match no real
model.

## Catch crossings it currently misses

Genuine crossings that never trip the join rule:

- **`prefetch_related`** - runs as a separate single-table query, so it never
  looks like a join.

## Surface queries the parser couldn't read

Some executed SQL can't be parsed, and right now those statements are skipped
silently. Need to collect and report them, so they can be found and either fixed or handled.

## Show how much was inspected

The plugin only sees queries that tests run, so a summary like "inspected N
queries across M tests" confirms the guard was active and how much was covered.


## Later

### Cheaper checking when ignores are set

With `[ignore]` entries, the plugin walks the call stack on every query, clean
ones included - a hot path on large suites worth making cheaper.

### Configurable project root

Ignore paths depend on where pytest thinks the root is, which can shift. Let the
config pin the root.
