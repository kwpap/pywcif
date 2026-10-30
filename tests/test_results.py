"""Result-related test placeholders."""

from __future__ import annotations

from pywcif import results


def test_results_module_importable() -> None:
    """Ensure the results module can be imported."""
    assert results is not None
