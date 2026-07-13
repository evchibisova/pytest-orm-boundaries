# Roadmap

Plan to improve. Not commitments - priorities can shift.


## Test supported versions in CI

Run the suite on every push and pull request across the supported Python/Django
matrix. Add a canary job for the next Django release, and publish only after a
green run.

## Add an end-to-end plugin test

Run pytest against a real sample project and assert the crossing report and
exit code, not just the individual components.

## Test for false positives

Cover cached and prefetched relations that issue no SQL, unrelated queries that
carry instance hints, and coexistence with other Django instrumentation.

## Report the application call site

Exclude the plugin's own frames so editable installs still point to the
application line that triggered the crossing.

## Catch crossings it currently misses

Genuine crossings that never trip the join rule:

- lazy reads such as `purchase.client`;
- reverse-FK and M2M reads such as `client.purchases.all()`;
- related writes such as `.create()`, `.add()`, `.set()`, `.remove()`,
  `.clear()`, `.update()`, and `.delete()`.


## Match ignores at the query site

Match ignores, including stale-ignore tracking, to the file that issues the
query rather than any file in its call chain. This also fixes false stale
reports in suites split across CI jobs: a shared file that other tests merely
pass through no longer counts the ignore as exercised, so a job that never
runs the crossing test stops reporting the ignore as stale.

## Warn about unknown models

Warn at startup when a model named in `boundaries.toml` does not exist.

## Add `orm-boundaries init`

Generate a deterministic starter `boundaries.toml` from installed Django
models. Suggest Django apps as an editable starting point, never overwrite an
existing file by default, and print the next step.

## Surface unparsed queries

Collect and report SQL statements the parser could not inspect instead of
silently skipping them.

## Show how much was inspected

Report the number of inspected queries and tests so users can see that the
guard ran and how much their suite exercised.

## Make ignore matching cheaper

Avoid walking the full call stack for every clean query when ignores are set.

## Make the project root configurable

Allow the config to pin the root used for matching file paths.

## Add SQLAlchemy support

Support SQLAlchemy as an alternative backend. Define how aggregates reference
mapped classes or table names while keeping ORM-specific dependencies optional.

## Measure instrumentation overhead

Benchmark the plugin on a large suite and publish the slowdown.
