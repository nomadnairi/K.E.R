"""
Update checker.

Compares the running version against the latest GitHub release (or a channel)
and reports whether an update is available, with a download URL. Network access
is injectable so the logic is fully unit-testable offline.

Actually *applying* an update is client-specific (the desktop app downloads and
launches the Windows installer); this module only decides *whether* and *where*.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass

from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

#: Default source repository for releases.
DEFAULT_REPO = "nomadnairi/J.A.R.V.I.S"


def parse_version(text: str) -> tuple[int, ...]:
    """Turn ``"v1.7.0"`` / ``"1.7"`` into a comparable tuple ``(1, 7, 0)``."""
    text = (text or "").strip().lstrip("vV").split("-")[0].split("+")[0]
    parts: list[int] = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """True if ``candidate`` is a strictly newer version than ``current``."""
    return parse_version(candidate) > parse_version(current)


@dataclass(frozen=True)
class UpdateInfo:
    """Result of an update check."""

    current: str
    latest: str
    available: bool
    url: str = ""
    download_url: str = ""
    sha256_url: str = ""
    notes: str = ""
    channel: str = "github"
    prerelease: bool = False

    def as_dict(self) -> dict:
        return {
            "current": self.current, "latest": self.latest,
            "available": self.available, "url": self.url,
            "download_url": self.download_url, "sha256_url": self.sha256_url,
            "notes": self.notes[:2000],
            "channel": self.channel, "prerelease": self.prerelease,
        }


def _http_json(url: str, timeout: int = 10):
    if not url.startswith("https://"):  # defensive
        raise ValueError("Refusing non-https update request.")
    req = urllib.request.Request(url, headers={
        "User-Agent": "jarvis-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
        return json.loads(resp.read().decode("utf-8"))


def download(url: str, dest: str, *, opener=None, chunk: int = 65536,
            on_progress=None) -> str:
    """Stream ``url`` to ``dest`` (installer download). Returns ``dest``.

    ``on_progress(done, total)`` is called as bytes arrive (total may be 0 if
    the server doesn't report a length). ``opener`` is injectable for testing.
    """
    if not url.startswith("https://"):
        raise ValueError("Refusing non-https download.")
    opener = opener or urllib.request.build_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-updater"})
    with opener.open(req) as resp:  # noqa: S310  # nosec B310
        total = int((resp.headers.get("Content-Length") if resp.headers else 0) or 0)
        done = 0
        with open(dest, "wb") as fh:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                if on_progress:
                    on_progress(done, total)
    return dest


def _pick_asset_dict(assets: list[dict], prefer: str = ".exe") -> dict:
    """Prefer an installer, then any matching-suffix asset, else the first."""
    for a in assets:
        if "setup" in a.get("name", "").lower() and a.get("name", "").endswith(prefer):
            return a
    for a in assets:
        if a.get("name", "").endswith(prefer):
            return a
    return assets[0] if assets else {}


def _pick_asset(assets: list[dict], prefer: str = ".exe") -> str:
    """Prefer an installer, then any matching-suffix asset, else the first."""
    return _pick_asset_dict(assets, prefer).get("browser_download_url", "")


def _asset_url_by_name(assets: list[dict], name: str) -> str:
    """Exact-match lookup, used to find an installer's checksum sibling."""
    for a in assets:
        if a.get("name", "") == name:
            return a.get("browser_download_url", "")
    return ""


def sha256_of_file(path: str, *, chunk: int = 65536) -> str:
    """Stream-hash a file on disk. Never reads it whole into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def fetch_checksum_text(url: str, *, opener=None, timeout: int = 10) -> str:
    """Download a small checksum file and return its raw text.

    Kept separate from parsing so tests can inject arbitrary content without
    a network stack. ``opener`` is injectable, same convention as
    :func:`download`.
    """
    if not url.startswith("https://"):
        raise ValueError("Refusing non-https checksum request.")
    opener = opener or urllib.request.build_opener()
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-updater"})
    with opener.open(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
        return resp.read().decode("utf-8", errors="replace")


def parse_sha256_text(text: str) -> str:
    """Extract a 64-hex-char digest from checksum-file text.

    Accepts a bare hex digest (what CI publishes: ``<hex>``) as well as the
    common ``sha256sum`` two-column format (``<hex>  filename``) some tools
    produce — the digest is always the first whitespace-separated token.
    Raises ``ValueError`` if nothing that looks like a SHA-256 digest is found,
    so a malformed or empty checksum file fails verification instead of
    silently comparing against an empty string.
    """
    token = text.strip().split()[0] if text.strip() else ""
    if len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise ValueError("Checksum file does not contain a valid SHA-256 digest.")
    return token.lower()


def verify_sha256(path: str, expected_hex: str) -> bool:
    """True iff the file at ``path`` hashes to ``expected_hex`` (case-insensitive)."""
    if not expected_hex:
        return False
    return sha256_of_file(path).lower() == expected_hex.strip().lower()


def check_github(current: str, *, repo: str = DEFAULT_REPO,
                include_prerelease: bool = True,
                asset_suffix: str = ".exe",
                fetch=_http_json) -> UpdateInfo:
    """Check the newest GitHub release for ``repo`` against ``current``.

    ``include_prerelease`` picks the newest release including pre-releases
    (the "early/grey" channel); otherwise only stable releases are considered.
    ``fetch`` is injectable for testing.
    """
    try:
        releases = fetch(f"https://api.github.com/repos/{repo}/releases?per_page=15")
    except Exception as exc:  # noqa: BLE001 - never crash the app on a check
        logger.debug("Update check failed: %s", exc)
        return UpdateInfo(current=current, latest=current, available=False)

    if isinstance(releases, dict):          # a single-release payload
        releases = [releases]
    best = None
    for rel in releases or []:
        if rel.get("draft"):
            continue
        if rel.get("prerelease") and not include_prerelease:
            continue
        tag = rel.get("tag_name", "")
        if best is None or is_newer(tag, best.get("tag_name", "")):
            best = rel
    if best is None:
        return UpdateInfo(current=current, latest=current, available=False)

    latest = best.get("tag_name", "")
    assets = best.get("assets", [])
    installer = _pick_asset_dict(assets, asset_suffix)
    download_url = installer.get("browser_download_url", "")
    sha256_url = ""
    if installer.get("name"):
        # CI publishes "<installer-name>.sha256" as a sibling release asset,
        # matched by the installer's own asset name (not its URL, which need
        # not share the same filename).
        sha256_url = _asset_url_by_name(assets, installer["name"] + ".sha256")
    return UpdateInfo(
        current=current, latest=latest,
        available=is_newer(latest, current),
        url=best.get("html_url", ""),
        download_url=download_url,
        sha256_url=sha256_url,
        notes=best.get("body", "") or "",
        channel="github",
        prerelease=bool(best.get("prerelease")),
    )
