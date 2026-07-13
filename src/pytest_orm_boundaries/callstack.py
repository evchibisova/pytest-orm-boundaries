"""Call-stack inspection: the in-project frames behind a query."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

# Installed deps live under these segments even when .venv is inside the project
# root, so match the segment, not the (varying) venv dir name.
_THIRD_PARTY_SEGMENTS = frozenset({"site-packages", "dist-packages"})


def _is_third_party(*, relative: Path) -> bool:
    """True if a root-relative path points into installed third-party code."""
    return not _THIRD_PARTY_SEGMENTS.isdisjoint(relative.parts)


def find_frames_inside_project(*, root: Path) -> list[tuple[str, int]]:
    """(root-relative path, line) for each in-project frame, innermost first.

    Skips stdlib (outside root) and installed packages; frames[0] is the line
    that issued the ORM call.
    """
    # Most frames behind an ORM query belong to Django, pytest, or the stdlib.
    # Reject them with a string-prefix check before constructing ``Path``
    # objects: on a real pytest stack that avoids dozens of allocations per
    # query. ``normcase`` keeps the prefix comparison correct on Windows.
    root_string = os.path.abspath(root)
    root_prefix = (
        root_string if root_string.endswith(os.sep) else root_string + os.sep
    )
    normalized_root_prefix = os.path.normcase(root_prefix)

    frames: list[tuple[str, int]] = []
    frame = inspect.currentframe()
    frame = frame.f_back if frame else None  # skip our own frame
    while frame is not None:
        filename = frame.f_code.co_filename
        if not os.path.normcase(filename).startswith(normalized_root_prefix):
            frame = frame.f_back
            continue
        relative = filename[len(root_prefix) :].replace(os.sep, "/")
        if not _THIRD_PARTY_SEGMENTS.isdisjoint(relative.split("/")):
            frame = frame.f_back
            continue
        frames.append((relative, frame.f_lineno))
        frame = frame.f_back
    return frames
