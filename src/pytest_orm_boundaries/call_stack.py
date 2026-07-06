"""Call-stack inspection: the in-project frames behind a query."""

from __future__ import annotations

import inspect
from pathlib import Path

# Installed deps live under these segments even when .venv is inside the project
# root, so match the segment, not the (varying) venv dir name.
_THIRD_PARTY_SEGMENTS = frozenset({"site-packages", "dist-packages"})


def _is_third_party(*, relative: Path) -> bool:
    """True if a root-relative path points into installed third-party code."""
    return not _THIRD_PARTY_SEGMENTS.isdisjoint(relative.parts)


def find_in_project_frames(*, root: Path) -> list[tuple[str, int]]:
    """(root-relative path, line) for each in-project frame, innermost first.

    Skips stdlib (outside root) and installed packages; frames[0] is the line
    that issued the ORM call.
    """
    frames: list[tuple[str, int]] = []
    frame = inspect.currentframe()
    frame = frame.f_back if frame else None  # skip our own frame
    while frame is not None:
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        frame = frame.f_back
        try:
            relative = Path(filename).relative_to(root)
        except ValueError:
            continue
        if _is_third_party(relative=relative):
            continue
        frames.append((relative.as_posix(), lineno))
    return frames
