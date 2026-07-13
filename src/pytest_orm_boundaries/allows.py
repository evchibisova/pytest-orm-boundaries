"""Per-file allows: files whose boundary crossings are intentional.

Unlike ``[ignore]`` (known debt, tracked for staleness), an ``[allow]`` marks
architecture that is meant to span aggregates - CQRS read models, cross-aggregate
reports - so a matching crossing is suppressed and never surfaces as stale.
"""

from __future__ import annotations

from collections.abc import Iterable
from fnmatch import fnmatch


class AllowList:
    """Decides whether a crossing's call place is intentional and so allowed.
    """

    def __init__(self, *, patterns: Iterable[str]) -> None:
        self._patterns = list(dict.fromkeys(patterns))  # ordered, de-duped

    @property
    def is_active(self) -> bool:
        return bool(self._patterns)

    def has_allow_for(self, *, file_paths: Iterable[str]) -> bool:
        return any(fnmatch(f, p) for f in file_paths for p in self._patterns)
