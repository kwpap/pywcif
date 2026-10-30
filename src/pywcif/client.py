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


def fetch_wcif(
    competition_id: str,
    *,
    oauth_token: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
    timeout: float = 15.0,
) -> Competition:
    """Download and validate a competition's WCIF from the WCA website.

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
        ValueError: If ``base_url`` does not use an http or https scheme, or if the response
            body is not a valid WCIF document (including invalid JSON).
        urllib.error.HTTPError: If the server answers with an error status (for example 404).
        urllib.error.URLError: If the request fails at the network level, including timeouts.
    """
    scheme = urllib.parse.urlsplit(base_url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"base_url must use http or https, got {base_url!r}")

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
        headers["Authorization"] = f"Bearer {oauth_token}"
    else:
        url = f"{root}/api/v0/competitions/{quoted_id}/wcif/public"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    data: Any = json.loads(body)
    return Competition.model_validate(data)


def load_wcif(source: str | Path | bytes | bytearray | dict[str, Any]) -> Competition:
    """Build a :class:`~pywcif.models.Competition` from a dict, JSON text, bytes, or a file.

    Args:
        source: One of:

            * a ``dict`` already decoded from WCIF JSON;
            * ``bytes`` or ``bytearray`` containing the JSON document (UTF-8);
            * a ``str`` whose stripped text starts with ``{`` and is parsed as JSON;
            * any other ``str`` or a :class:`pathlib.Path`, read as a UTF-8 file.

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
        return Competition.model_validate_json(source)
    if isinstance(source, Path):
        return _load_file(source)
    if source.lstrip().startswith("{"):
        return Competition.model_validate_json(source)
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
    """Read a UTF-8 WCIF JSON file and validate it."""
    return Competition.model_validate_json(path.read_text(encoding="utf-8"))
