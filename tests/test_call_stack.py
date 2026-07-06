"""Call-stack inspection: project frames and third-party-path filtering."""

from pathlib import Path

from pytest_orm_boundaries.call_stack import _is_third_party, find_in_project_frames


def test_project_frames_pin_the_call_place_with_a_line():
    root = Path(__file__).resolve().parents[1]
    frames = find_in_project_frames(root=root)
    file, line = frames[0]  # innermost project frame == this call place
    assert file == "tests/test_call_stack.py"
    assert line > 0


def test_third_party_paths_are_not_project_files():
    django_frame = Path(".venv/lib/python3.12/site-packages/django/db/models/query.py")
    assert _is_third_party(relative=django_frame) is True
    assert _is_third_party(relative=Path("payrolls/domain/pay_by_url.py")) is False


def test_project_frames_exclude_installed_packages():
    # pytest itself runs from site-packages inside the repo's .venv (under root),
    # so its frames must be filtered out rather than taken as the call place.
    root = Path(__file__).resolve().parents[1]
    frames = find_in_project_frames(root=root)
    assert all("site-packages" not in file for file, _ in frames)
