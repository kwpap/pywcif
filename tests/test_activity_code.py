"""Activity code parsing test placeholders."""

from __future__ import annotations

from pywcif import activity_code


def test_activity_code_module_importable() -> None:
    """Ensure the activity code module can be imported."""
    assert activity_code is not None
