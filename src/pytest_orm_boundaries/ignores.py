"""Per-file ignores at runtime: the IgnoreTracker book-keeping."""

from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatch


class IgnoreTracker:
    """Decides whether a crossing is ignored, and reports ignore globs that went
    stale - their file ran but never crossed a boundary."""

    def __init__(self, *, patterns: Iterable[str]) -> None:
        self._patterns = list(dict.fromkeys(patterns))  # ordered, de-duped
        self._seen: set[str] = set()  # patterns executed during the run
        self._used: set[str] = set()  # ...that also crossed a boundary

    @property
    def is_active(self) -> bool:
        return bool(self._patterns)

    def mark_seen(self, *, file_paths: Iterable[str]) -> None:
        self._seen.update(self._find_matching_patterns(file_paths))

    def mark_used(self, *, file_paths: Iterable[str]) -> None:
        self._used.update(self._find_matching_patterns(file_paths))

    def has_ignore_for(self, *, file_paths: Iterable[str]) -> bool:
        return bool(self._find_matching_patterns(file_paths))

    def find_stale_patterns(self) -> list[str]:
        return sorted(self._seen - self._used)

    def export_matched_patterns(self) -> tuple[set[str], set[str]]:
        """Return copies of the patterns seen and used during this run."""
        return set(self._seen), set(self._used)

    def merge_matched_patterns(
        self, *, seen: Iterable[str], used: Iterable[str]
    ) -> None:
        """Merge ignore activity collected by another process."""
        self._seen.update(seen)
        self._used.update(used)

    def _find_matching_patterns(self, file_paths: Iterable[str]) -> set[str]:
        return {p for f in file_paths for p in self._patterns if fnmatch(f, p)}
