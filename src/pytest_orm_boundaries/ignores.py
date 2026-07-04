"""Per-file ignores at runtime: the tracker and call-stack inspection."""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path


class IgnoreTracker:
    """Decides whether a violation is ignored, and reports ignore globs that went
    stale - their file ran but never crossed a boundary."""

    def __init__(self, *, patterns: Iterable[str], root: Path) -> None:
        self.root = Path(root)
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

    def _find_matching_patterns(self, file_paths: Iterable[str]) -> set[str]:
        return {p for f in file_paths for p in self._patterns if fnmatch(f, p)}


def find_source_files_in_stack(*, root: Path) -> list[str]:
    """Root-relative (posix) paths of project files on the current call stack.

    Frames outside ``root`` (Django, pytest, stdlib) are skipped, leaving the
    application/test files that led to this query.
    """
    files: list[str] = []
    seen: set[str] = set()
    frame = inspect.currentframe()
    frame = frame.f_back if frame else None  # start at the caller, skip our own frame
    while frame is not None:
        filename = frame.f_code.co_filename
        frame = frame.f_back  # for next iteration
        if filename in seen:
            continue
        seen.add(filename)
        try:
            files.append(Path(filename).relative_to(root).as_posix())
        except ValueError:
            continue
    return files
