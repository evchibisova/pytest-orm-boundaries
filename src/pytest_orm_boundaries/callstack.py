"""Call-stack inspection: the in-project frames behind a query."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Installed deps live under these segments even when .venv is inside the project
# root, so match the segment, not the (varying) venv dir name.
_THIRD_PARTY_SEGMENTS = frozenset({"site-packages", "dist-packages"})
_MAX_REPORTED_STACK_FRAMES = 5


@dataclass(frozen=True, order=True)
class ProjectStackFrame:
    """One project-owned frame in the stack behind a query."""

    file: str
    line_number: int
    function: str


def _is_third_party(*, relative: Path) -> bool:
    """True if a root-relative path points into installed third-party code."""
    return not _THIRD_PARTY_SEGMENTS.isdisjoint(relative.parts)


def find_frames_inside_project(*, root: Path) -> list[ProjectStackFrame]:
    """Project-owned frames, innermost first.

    Skips stdlib (outside root) and installed packages; frames[0] is the line
    that issued the ORM call.
    """
    frames: list[ProjectStackFrame] = []
    frame = inspect.currentframe()
    frame = frame.f_back if frame else None  # skip our own frame
    while frame is not None:
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        function = frame.f_code.co_qualname
        frame = frame.f_back
        try:
            relative = Path(filename).relative_to(root)
        except ValueError:
            continue
        if _is_third_party(relative=relative):
            continue
        frames.append(
            ProjectStackFrame(
                file=relative.as_posix(),
                line_number=lineno,
                function=function,
            )
        )
    return frames


def select_callers_for_report(
    *, frames: Sequence[ProjectStackFrame], test: str | None
) -> tuple[ProjectStackFrame, ...]:
    """Select callers after the execution frame, stopping before the test.

    Matching allow/ignore patterns uses the complete frame list. Only the
    diagnostic chain returned here is capped.
    """
    test_file = test.partition("::")[0].replace("\\", "/") if test else None
    callers: list[ProjectStackFrame] = []
    for frame in frames[1:]:
        if test_file is not None and frame.file == test_file:
            break
        callers.append(frame)
        if len(callers) == _MAX_REPORTED_STACK_FRAMES - 1:
            break
    return tuple(callers)
