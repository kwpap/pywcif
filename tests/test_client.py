"""Tests for the HTTP client, the WCIF loaders, and the public package API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

import pywcif
from pywcif import Competition, dump_wcif, fetch_wcif, load_wcif

MINIMAL_WCIF: dict[str, Any] = {
    "formatVersion": "1.0",
    "id": "TestComp2026",
    "name": "Test Competition 2026",
    "shortName": "Test 2026",
    "competitorLimit": None,
    "persons": [],
    "events": [],
    "extensions": [],
    "schedule": {"startDate": "2026-07-01", "numberOfDays": 1, "venues": []},
}

BASE = "https://www.worldcubeassociation.org"


class _FakeResponse:
    """Minimal stand-in for the object returned by ``urllib.request.urlopen``."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeUrlopen:
    """Records every request and returns a canned body (or raises a canned error)."""

    def __init__(self, body: bytes, error: Exception | None = None) -> None:
        self.body = body
        self.error = error
        self.calls: list[tuple[urllib.request.Request, float | None]] = []

    def __call__(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> _FakeResponse:
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return _FakeResponse(self.body)


def _headers(request: urllib.request.Request) -> dict[str, str]:
    """Return request headers keyed by lowercase name (urllib capitalizes them oddly)."""
    return {name.lower(): value for name, value in request.header_items()}


@pytest.fixture
def fake_urlopen(monkeypatch: pytest.MonkeyPatch) -> _FakeUrlopen:
    fake = _FakeUrlopen(json.dumps(MINIMAL_WCIF).encode("utf-8"))
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


# ---------------------------------------------------------------------------
# fetch_wcif
# ---------------------------------------------------------------------------


def test_fetch_public_url_without_token(fake_urlopen: _FakeUrlopen) -> None:
    comp = fetch_wcif("TestComp2026")

    assert isinstance(comp, Competition)
    assert comp.id == "TestComp2026"
    assert len(fake_urlopen.calls) == 1
    request, _ = fake_urlopen.calls[0]
    assert request.full_url == f"{BASE}/api/v0/competitions/TestComp2026/wcif/public"
    assert "authorization" not in _headers(request)


def test_fetch_private_url_with_token_sends_bearer_header(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026", oauth_token="secret-token")

    request, _ = fake_urlopen.calls[0]
    assert request.full_url == f"{BASE}/api/v0/competitions/TestComp2026/wcif"
    assert _headers(request)["authorization"] == "Bearer secret-token"


def test_empty_token_is_treated_as_no_token(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026", oauth_token="")

    request, _ = fake_urlopen.calls[0]
    assert request.full_url.endswith("/wcif/public")
    assert "authorization" not in _headers(request)


def test_fetch_sends_accept_and_user_agent_headers(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026")

    headers = _headers(fake_urlopen.calls[0][0])
    assert headers["accept"] == "application/json"
    assert headers["user-agent"] == f"pywcif/{pywcif.__version__}"


@pytest.mark.parametrize("base_url", [BASE, BASE + "/", BASE + "///"])
def test_base_url_trailing_slashes_are_stripped(fake_urlopen: _FakeUrlopen, base_url: str) -> None:
    fetch_wcif("TestComp2026", base_url=base_url)

    assert fake_urlopen.calls[0][0].full_url == (
        f"{BASE}/api/v0/competitions/TestComp2026/wcif/public"
    )


def test_custom_base_url_is_used(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026", base_url="http://localhost:8000/", oauth_token="t")

    assert fake_urlopen.calls[0][0].full_url == (
        "http://localhost:8000/api/v0/competitions/TestComp2026/wcif"
    )


def test_competition_id_is_url_quoted(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("My Comp/x?y")

    assert fake_urlopen.calls[0][0].full_url == (
        f"{BASE}/api/v0/competitions/My%20Comp%2Fx%3Fy/wcif/public"
    )


def test_timeout_is_passed_through(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026", timeout=3.5)

    assert fake_urlopen.calls[0][1] == 3.5


def test_default_timeout_is_15_seconds(fake_urlopen: _FakeUrlopen) -> None:
    fetch_wcif("TestComp2026")

    assert fake_urlopen.calls[0][1] == 15.0


@pytest.mark.parametrize("base_url", ["ftp://example.test", "file:///etc", "example.test"])
def test_invalid_base_url_scheme_raises_value_error(
    fake_urlopen: _FakeUrlopen, base_url: str
) -> None:
    with pytest.raises(ValueError, match="http or https"):
        fetch_wcif("TestComp2026", base_url=base_url)
    assert fake_urlopen.calls == []


def test_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError(
        url=f"{BASE}/api/v0/competitions/Nope/wcif/public",
        code=404,
        msg="Not Found",
        hdrs=Message(),
        fp=None,
    )
    monkeypatch.setattr(urllib.request, "urlopen", _FakeUrlopen(b"", error=error))

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        fetch_wcif("Nope")
    assert excinfo.value.code == 404


def test_invalid_body_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _FakeUrlopen(b'{"id": "x"}'))

    with pytest.raises(ValueError):
        fetch_wcif("TestComp2026")


# ---------------------------------------------------------------------------
# load_wcif
# ---------------------------------------------------------------------------


def test_load_from_dict() -> None:
    comp = load_wcif(MINIMAL_WCIF)

    assert isinstance(comp, Competition)
    assert comp.id == "TestComp2026"
    assert comp.short_name == "Test 2026"


def test_load_from_json_str() -> None:
    comp = load_wcif(json.dumps(MINIMAL_WCIF, indent=2))

    assert comp.to_wcif_dict() == MINIMAL_WCIF


def test_load_from_json_str_with_leading_whitespace() -> None:
    comp = load_wcif("\n  " + json.dumps(MINIMAL_WCIF))

    assert comp.id == "TestComp2026"


def test_load_from_bytes() -> None:
    comp = load_wcif(json.dumps(MINIMAL_WCIF).encode("utf-8"))

    assert comp.to_wcif_dict() == MINIMAL_WCIF


def test_load_from_bytearray() -> None:
    comp = load_wcif(bytearray(json.dumps(MINIMAL_WCIF).encode("utf-8")))

    assert comp.name == "Test Competition 2026"


def test_load_from_str_path(tmp_path: Path) -> None:
    path = tmp_path / "wcif.json"
    path.write_text(json.dumps(MINIMAL_WCIF), encoding="utf-8")

    comp = load_wcif(str(path))

    assert comp.to_wcif_dict() == MINIMAL_WCIF


def test_load_from_path_object(tmp_path: Path) -> None:
    path = tmp_path / "wcif.json"
    path.write_text(json.dumps(MINIMAL_WCIF), encoding="utf-8")

    comp = load_wcif(path)

    assert comp.to_wcif_dict() == MINIMAL_WCIF


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_wcif(tmp_path / "does-not-exist.json")


def test_load_invalid_json_str_raises_value_error() -> None:
    with pytest.raises(ValueError):
        load_wcif('{"id": ')


# ---------------------------------------------------------------------------
# dump_wcif
# ---------------------------------------------------------------------------


def test_dump_returns_text_matching_to_wcif_json() -> None:
    comp = load_wcif(MINIMAL_WCIF)

    text = dump_wcif(comp)

    assert text == comp.to_wcif_json(indent=2)
    assert json.loads(text) == MINIMAL_WCIF


def test_dump_compact_when_indent_is_none() -> None:
    comp = load_wcif(MINIMAL_WCIF)

    text = dump_wcif(comp, indent=None)

    assert "\n" not in text
    assert json.loads(text) == MINIMAL_WCIF


def test_dump_writes_file_that_loads_back_equal(tmp_path: Path) -> None:
    comp = load_wcif(MINIMAL_WCIF)
    path = tmp_path / "out.json"

    text = dump_wcif(comp, path)

    assert path.read_text(encoding="utf-8") == text
    reloaded = load_wcif(path)
    assert reloaded == comp
    assert reloaded.to_wcif_dict() == MINIMAL_WCIF


def test_dump_accepts_str_path(tmp_path: Path) -> None:
    comp = load_wcif(MINIMAL_WCIF)
    path = tmp_path / "out.json"

    dump_wcif(comp, str(path))

    assert load_wcif(str(path)).to_wcif_dict() == MINIMAL_WCIF


# ---------------------------------------------------------------------------
# Public package API
# ---------------------------------------------------------------------------


def test_all_names_are_attributes_of_package() -> None:
    missing = [name for name in pywcif.__all__ if not hasattr(pywcif, name)]

    assert missing == []


def test_all_has_no_duplicates() -> None:
    assert len(pywcif.__all__) == len(set(pywcif.__all__))


def test_version_is_0_1_0() -> None:
    assert pywcif.__version__ == "0.1.0"
