"""HTTP client and file/JSON loaders for WCIF documents.

The HTTP client uses only the standard library (``urllib.request``). Network errors are not
wrapped: ``urllib.error.HTTPError`` (a non-2xx response) and ``urllib.error.URLError`` (DNS,
connection or timeout failures) propagate to the caller.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from pywcif.models import Competition

_DEFAULT_BASE_URL = "https://www.worldcubeassociation.org"
_ALLOWED_SCHEMES = frozenset({"http", "https"})
# Hosts where sending a token over plain http is acceptable (a local WCA development server).
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def fetch_wcif(
    competition_id: str,
    *,
    oauth_token: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
    timeout: float = 15.0,
) -> Competition:
    """Download and validate a competition's WCIF from the WCA website.

    This is :func:`fetch_wcif_dict` followed by ``Competition.model_validate``.

    Without a token the public endpoint ``/api/v0/competitions/{id}/wcif/public`` is used.
    With a token the private endpoint ``/api/v0/competitions/{id}/wcif`` is used and the
    token is sent as ``Authorization: Bearer <token>``. An empty token is treated as no token.

    Args:
        competition_id: WCA competition id, e.g. ``"WCA2026Example"``. It is URL-quoted.
        oauth_token: Optional OAuth access token with permission to read the WCIF.
        base_url: Site root. A trailing ``/`` is ignored. Must use ``http`` or ``https``.
        timeout: Socket timeout in seconds, passed to ``urllib.request.urlopen``.

    Returns:
        The parsed and validated :class:`~pywcif.models.Competition`.

    Raises:
        ValueError: If ``base_url`` does not use an http or https scheme, if a token would be
            sent over plain http to a non-loopback host, or if the response body is not a
            valid WCIF document (including invalid JSON).
        urllib.error.HTTPError: If the server answers with an error status (for example 404).
        urllib.error.URLError: If the request fails at the network level, including timeouts.
    """
    data = fetch_wcif_dict(
        competition_id, oauth_token=oauth_token, base_url=base_url, timeout=timeout
    )
    return Competition.model_validate(data)


def fetch_wcif_dict(
    competition_id: str,
    *,
    oauth_token: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Download a competition's WCIF as the raw decoded JSON dict, without validation.

    Takes the same arguments as :func:`fetch_wcif`. Useful for snapshotting payloads or
    comparing them with ``Competition.to_wcif_dict()``.

    Raises:
        ValueError: If ``base_url`` does not use an http or https scheme, if a token would be
            sent over plain http to a non-loopback host, or if the body is not a JSON object.
        urllib.error.HTTPError: If the server answers with an error status (for example 404).
        urllib.error.URLError: If the request fails at the network level, including timeouts.
    """
    parts = urllib.parse.urlsplit(base_url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"base_url must use http or https, got {base_url!r}")
    if oauth_token and scheme != "https" and parts.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"refusing to send an OAuth token over plain http to {base_url!r}; use https"
        )

    # Imported here because pywcif/__init__.py imports this module before it defines __version__.
    from pywcif import __version__

    root = base_url.rstrip("/")
    quoted_id = urllib.parse.quote(competition_id, safe="")
    headers = {
        "Accept": "application/json",
        "User-Agent": f"pywcif/{__version__}",
    }
    if oauth_token:
        url = f"{root}/api/v0/competitions/{quoted_id}/wcif"
    else:
        url = f"{root}/api/v0/competitions/{quoted_id}/wcif/public"

    request = urllib.request.Request(url, headers=headers)
    if oauth_token:
        # Unredirected headers are not copied onto redirects, so a redirect to another host
        # (or down to http) never receives the token.
        request.add_unredirected_header("Authorization", f"Bearer {oauth_token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    data: Any = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    return data


def load_wcif(source: str | Path | bytes | bytearray | dict[str, Any]) -> Competition:
    """Build a :class:`~pywcif.models.Competition` from a dict, JSON text, bytes, or a file.

    Args:
        source: One of:

            * a ``dict`` already decoded from WCIF JSON;
            * ``bytes`` or ``bytearray`` containing the JSON document (UTF-8);
            * a ``str`` whose stripped text starts with ``{`` or ``[``, parsed as JSON;
            * any other ``str`` or a :class:`pathlib.Path`, read as a UTF-8 file.

            A leading UTF-8 byte-order mark is ignored in every form.

    Returns:
        The validated competition.

    Raises:
        ValueError: If the content is not valid WCIF (pydantic's ``ValidationError`` is a
            ``ValueError``, as is invalid JSON).
        FileNotFoundError: If a path is given and the file does not exist.
    """
    if isinstance(source, dict):
        return Competition.model_validate(source)
    if isinstance(source, (bytes, bytearray)):
        return _validate_json_text(bytes(source).decode("utf-8-sig"))
    if isinstance(source, Path):
        return _load_file(source)
    if source.lstrip("\ufeff \t\r\n").startswith(("{", "[")):
        return _validate_json_text(source)
    return _load_file(Path(source))


def dump_wcif(
    comp: Competition,
    path: str | Path | None = None,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a competition to WCIF JSON, optionally writing it to a file.

    Args:
        comp: The competition to serialize.
        path: If given, the JSON text is also written to this path as UTF-8.
        indent: Indentation passed to ``json`` formatting. ``None`` produces compact output.

    Returns:
        The WCIF JSON document as a string.
    """
    text = comp.to_wcif_json(indent=indent)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def _load_file(path: Path) -> Competition:
    """Read a UTF-8 WCIF JSON file (a leading byte-order mark is allowed) and validate it."""
    return _validate_json_text(path.read_text(encoding="utf-8-sig"))


def _validate_json_text(text: str) -> Competition:
    """Validate JSON text, ignoring a leading byte-order mark (common in Windows editors)."""
    return Competition.model_validate_json(text.lstrip("\ufeff"))
