# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.4] - 2026-07-22

### Changed

- Separate boundary-crossing locations with blank lines and show at most three
  affected tests per location unless verbose output is enabled.

## [0.7.3] - 2026-07-13

### Fixed

- Merge boundary crossings and stale-ignore activity from `pytest-xdist`
  workers so parallel runs report violations and exit non-zero like serial runs.

## [0.7.2] - 2026-07-13

### Fixed

- Skip `prefetch_related` boundary analysis for rows produced by `values()` and
  `values_list()` instead of crashing on their non-model types.

## [0.7.1] - 2026-07-13

### Changed

- Update documentation.

## [0.7.0] - 2026-07-13

### Changed

- Aggregate definitions in `boundaries.toml` use an `[aggregates.<name>]`
  section with a required `models` list.

## [0.6.0] - 2026-07-13

### Added

- `[allow]` section in `boundaries.toml`: files whose crossings are intentional
  (CQRS read models, cross-aggregate reports). Suppressed like `[ignore]` but
  never reported as stale. When a file is listed in both, the allow wins and the
  redundant `[ignore]` entry surfaces as stale.

## [0.5.0] - 2026-07-12

### Added

- Catch `prefetch_related` crossings.

### Changed

- Django is pulled in through the optional `django` extra
  (`pip install "pytest-orm-boundaries[django]"`). The plugin no longer fails to import when Django is absent - it warns and runs no checks.

## [0.4.0] - 2026-07-11

### Added

- Catch more crossings: `select_related`, subqueries, and hand-written SQL (`.raw()`, `cursor.execute(...)`).

### Changed

- Detection now parses the SQL each query executes, via Django's public
  `connection.execute_wrapper` hook. Adds a dependency on
  [`sqlglot`](https://github.com/tobymao/sqlglot).

## [0.3.1] - 2026-07-07

### Changed

- Clearer boundary report: each offending place now shows the crossed aggregates and the joined models.

## [0.3.0] - 2026-07-06

### Changed

- A boundary crossing no longer fails the individual test. The plugin now
  collects all crossings and prints one grouped report at the end of the run.

### Fixed

- Stack inspection no longer treats installed packages as project code: frames under `site-packages`/`dist-packages` are skipped, so the reported place points at application code.
- Filtering by a foreign-key id no longer raises a false `BoundaryViolation`:
  the linked table is planned but never actually read, so it isn't a crossing.

## [0.2.0] - 2026-07-04

### Added

- Per-file ignores: an `[ignore] files` list of globs in `boundaries.toml`.
- Stale-ignore hint: when an ignored file runs without any crossing, the plugin
  reports it at the end of the session.

## [0.1.0] - 2026-06-24

Initial alpha release.

### Added

- Django ORM support: detects cross-aggregate access in the queries your test suite
  executes.

[0.7.4]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.7.3...v0.7.4
[0.7.3]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/evchibisova/pytest-orm-boundaries/releases/tag/v0.1.0
