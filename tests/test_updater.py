"""Tests for the update checker (offline, injected fetch)."""

from __future__ import annotations

import pytest

from jarvis.core.updater import (
    UpdateInfo,
    check_github,
    fetch_checksum_text,
    is_newer,
    parse_sha256_text,
    parse_version,
    sha256_of_file,
    verify_sha256,
)


def test_parse_and_compare_versions():
    assert parse_version("v1.7.0") == (1, 7, 0)
    assert parse_version("1.7") == (1, 7, 0)
    assert parse_version("2.0.1-beta") == (2, 0, 1)
    assert is_newer("1.7.1", "1.7.0") is True
    assert is_newer("1.7.0", "1.7.0") is False
    assert is_newer("1.6.9", "1.7.0") is False


_RELEASES = [
    {"tag_name": "v1.7.0", "prerelease": True, "draft": False,
    "html_url": "https://gh/rel/1.7.0", "body": "notes",
    "assets": [{"name": "JARVIS-Setup.exe",
                "browser_download_url": "https://gh/dl/setup.exe"},
                {"name": "JARVIS-Setup.exe.sha256",
                "browser_download_url": "https://gh/dl/setup.exe.sha256"},
                {"name": "JARVIS-windows-amd64.exe",
                "browser_download_url": "https://gh/dl/portable.exe"}]},
    {"tag_name": "v1.6.0", "prerelease": False, "draft": False,
    "html_url": "https://gh/rel/1.6.0", "body": "", "assets": []},
]


def test_check_finds_newer_prerelease():
    info = check_github("1.6.5", include_prerelease=True,
                        fetch=lambda url: _RELEASES)
    assert info.available is True and info.latest == "v1.7.0"
    assert info.prerelease is True
    # Installer asset is preferred for the download link.
    assert info.download_url == "https://gh/dl/setup.exe"
    # Its checksum sibling is matched by the installer's asset *name*
    # ("JARVIS-Setup.exe" + ".sha256"), not by parsing its download URL —
    # the fixture deliberately gives them unrelated URL slugs.
    assert info.sha256_url == "https://gh/dl/setup.exe.sha256"


def test_check_leaves_sha256_url_empty_when_no_sibling_asset():
    releases = [{"tag_name": "v2.0.0", "prerelease": False, "draft": False,
                "html_url": "https://gh/rel/2.0.0", "body": "",
                "assets": [{"name": "JARVIS-Setup.exe",
                            "browser_download_url": "https://gh/dl/2/setup.exe"}]}]
    info = check_github("1.0.0", fetch=lambda url: releases)
    assert info.download_url == "https://gh/dl/2/setup.exe"
    assert info.sha256_url == ""


def test_stable_channel_ignores_prerelease():
    info = check_github("1.5.0", include_prerelease=False,
                        fetch=lambda url: _RELEASES)
    assert info.latest == "v1.6.0" and info.available is True


def test_no_update_when_current_is_latest():
    info = check_github("1.7.0", include_prerelease=True,
                        fetch=lambda url: _RELEASES)
    assert info.available is False


def test_network_failure_is_soft():
    def boom(url):
        raise OSError("no network")
    info = check_github("1.7.0", fetch=boom)
    assert isinstance(info, UpdateInfo) and info.available is False


def test_download_streams_to_file(tmp_path):
    import io

    from jarvis.core.updater import download

    class FakeResp(io.BytesIO):
        headers = {"Content-Length": "10"}
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    class FakeOpener:
        def open(self, req):
            return FakeResp(b"0123456789")

    seen = []
    dest = tmp_path / "setup.exe"
    out = download("https://x/setup.exe", str(dest), opener=FakeOpener(),
                on_progress=lambda d, t: seen.append((d, t)))
    assert out == str(dest)
    assert dest.read_bytes() == b"0123456789"
    assert seen[-1] == (10, 10)


def test_download_rejects_non_https(tmp_path):
    from jarvis.core.updater import download
    import pytest as _pt
    with _pt.raises(ValueError):
        download("http://x/setup.exe", str(tmp_path / "s.exe"))


# -- integrity verification (jarvis/core/updater.py) ---------------------------


def test_sha256_of_file_matches_hashlib(tmp_path):
    import hashlib

    path = tmp_path / "setup.exe"
    path.write_bytes(b"totally a real installer" * 1000)
    assert sha256_of_file(str(path)) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_verify_sha256_accepts_matching_digest_case_insensitively(tmp_path):
    path = tmp_path / "setup.exe"
    path.write_bytes(b"payload")
    digest = sha256_of_file(str(path))
    assert verify_sha256(str(path), digest) is True
    assert verify_sha256(str(path), digest.upper()) is True


def test_verify_sha256_rejects_tampered_file(tmp_path):
    path = tmp_path / "setup.exe"
    path.write_bytes(b"payload")
    digest = sha256_of_file(str(path))
    path.write_bytes(b"tampered payload")  # file changed after the digest was taken
    assert verify_sha256(str(path), digest) is False


def test_verify_sha256_rejects_empty_expected_digest(tmp_path):
    """A missing/blank checksum must never be treated as a pass."""
    path = tmp_path / "setup.exe"
    path.write_bytes(b"payload")
    assert verify_sha256(str(path), "") is False


def test_parse_sha256_text_accepts_bare_digest():
    digest = "a" * 64
    assert parse_sha256_text(digest) == digest
    assert parse_sha256_text(digest.upper()) == digest  # normalized to lowercase
    assert parse_sha256_text(f"  {digest}  \n") == digest


def test_parse_sha256_text_accepts_sha256sum_two_column_format():
    digest = "b" * 64
    assert parse_sha256_text(f"{digest}  JARVIS-Setup.exe\n") == digest


def test_parse_sha256_text_rejects_garbage():
    with pytest.raises(ValueError):
        parse_sha256_text("not a checksum file")
    with pytest.raises(ValueError):
        parse_sha256_text("")
    with pytest.raises(ValueError):
        parse_sha256_text("g" * 64)  # right length, not hex


def test_fetch_checksum_text_rejects_non_https():
    with pytest.raises(ValueError):
        fetch_checksum_text("http://x/setup.exe.sha256")


def test_fetch_checksum_text_reads_body_via_injected_opener():
    import io

    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    class FakeOpener:
        def open(self, req, timeout=None):
            return FakeResp(b"c" * 64)

    text = fetch_checksum_text("https://gh/dl/setup.exe.sha256", opener=FakeOpener())
    assert text == "c" * 64


def test_end_to_end_tampered_download_fails_verification(tmp_path):
    """The exact scenario the auto-updater must refuse to run."""
    genuine = tmp_path / "genuine.exe"
    genuine.write_bytes(b"the real installer bytes")
    published_digest = sha256_of_file(str(genuine))

    tampered = tmp_path / "downloaded.exe"
    tampered.write_bytes(b"a different, tampered installer")

    assert verify_sha256(str(tampered), published_digest) is False
