"""Audit-related test placeholders."""

from __future__ import annotations

from pywcif import audit


def test_audit_module_importable() -> None:
    """Ensure the audit module can be imported."""
    assert audit is not None
