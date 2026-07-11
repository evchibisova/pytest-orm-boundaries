"""Call-stack inspection: project frames and third-party-path filtering."""

from pathlib import Path

from pytest_orm_boundaries.callstack import _is_third_party, find_frames_inside_project


def test_project_frames_pin_the_call_place_with_a_line():
    root = Path(__file__).resolve().parents[1]
    frames = find_frames_inside_project(root=root)
    file, line = frames[0]  # innermost project frame == this call place
    assert file == "tests/test_callstack.py"
    assert line > 0


def test_third_party_paths_are_not_project_files():
    django_frame = Path(".venv/lib/python3.12/site-packages/django/db/models/query.py")
    assert _is_third_party(relative=django_frame) is True
    assert _is_third_party(relative=Path("payrolls/domain/pay_by_url.py")) is False


def test_project_frames_exclude_installed_packages():
    # pytest itself runs from site-packages inside the repo's .venv (under root),
    # so its frames must be filtered out rather than taken as the call place.
    root = Path(__file__).resolve().parents[1]
    frames = find_frames_inside_project(root=root)
    assert all("site-packages" not in file for file, _ in frames)
