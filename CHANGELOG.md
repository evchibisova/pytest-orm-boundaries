# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-07-05

### Fixed

- Filtering by a foreign-key id no longer raises a false `BoundaryViolation`:
  the linked table is planned but never actually read, so it isn't a crossing.

## [0.2.0] - 2026-07-04

### Added

- Per-file ignores: an `[ignore] files` list of globs in `boundaries.toml`.
- Stale-ignore hint: when an ignored file runs without any violation, the plugin
  reports it at the end of the session.

## [0.1.0] - 2026-06-24

Initial alpha release.

### Added

- Django ORM support: detects cross-aggregate access in the queries your test suite
  executes.

[Unreleased]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/evchibisova/pytest-orm-boundaries/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/evchibisova/pytest-orm-boundaries/releases/tag/v0.1.0
