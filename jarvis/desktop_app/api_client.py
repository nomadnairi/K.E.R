"""
Minimal synchronous client for the J.A.R.V.I.S. HTTP API (remote mode).

Standard library only (``urllib``), so the packaged .exe needs no extra HTTP
dependency. Used by the desktop app's login screen and remote chat, and by the
Android client's reference implementation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    """The server rejected a request (carries the HTTP status)."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class JarvisApiClient:
    """Talk to a remote J.A.R.V.I.S. server."""

    def __init__(self, base_url: str, *, token: str = "",
                timeout: float = 60.0) -> None:
        base_url = base_url.rstrip("/")
        scheme = urllib.parse.urlparse(base_url).scheme
        if scheme not in ("http", "https"):
            # Reject file:, ftp:, etc. so a bad config can't read local files.
            raise ApiError(0, "Server URL must start with http:// or https://.")
        self.base_url = base_url
        self.token = token
        self._timeout = timeout

    # -- plumbing -------------------------------------------------------------

    def _request(self, method: str, path: str,
                body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            # Scheme validated to http/https in __init__ (no file:/ SSRF).
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:  # noqa: S310  # nosec B310
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                payload = json.loads(exc.read() or b"{}")
                detail = str(payload.get("detail", ""))
            except (json.JSONDecodeError, OSError):
                pass
            raise ApiError(exc.code, detail or f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(0, f"Cannot reach server: {exc.reason}") from exc

    # -- endpoints ------------------------------------------------------------

    def info(self) -> dict:
        return self._request("GET", "/")

    def health(self) -> dict:
        return self._request("GET", "/health")

    def login(self, username: str, password: str) -> str:
        """Sign in; stores and returns the bearer token."""
        out = self._request("POST", "/auth/login",
                            {"username": username, "password": password})
        self.token = out["token"]
        return self.token

    def register(self, username: str, password: str) -> str:
        """Create an account and sign in with it; stores the token."""
        out = self._request("POST", "/auth/register",
                            {"username": username, "password": password})
        self.token = out["token"]
        return self.token

    def login_with_telegram_code(self, code: str) -> str:
        """Sign in with a bot-issued Telegram login code; stores the token."""
        out = self._request("POST", "/auth/telegram", {"code": code.strip()})
        self.token = out["token"]
        return self.token

    def me(self) -> dict:
        return self._request("GET", "/auth/me")

    def logout(self) -> None:
        try:
            self._request("POST", "/auth/logout")
        finally:
            self.token = ""

    def pairing_code(self) -> str:
        """Get a code to link Telegram (send /link CODE to the bot)."""
        return self._request("POST", "/auth/pairing-code")["code"]

    # -- API keys (the credential behind the hosted proxy) --------------------

    def list_api_keys(self) -> list[dict]:
        """The account's live API keys — metadata only, never the secret."""
        return self._request("GET", "/auth/api-keys").get("keys", [])

    def create_api_key(self, label: str = "") -> str:
        """Mint a key; the plaintext is returned once and never again."""
        return self._request("POST", "/auth/api-keys", {"label": label})["key"]

    def revoke_api_key(self, key_id: int) -> None:
        """Revoke one of the account's keys (effective on the next request)."""
        self._request("DELETE", f"/auth/api-keys/{int(key_id)}")

    def chat(self, message: str, session_id: str = "desktop") -> str:
        out = self._request("POST", "/chat",
                            {"message": message, "session_id": session_id})
        return out["reply"]

    def chat_stream(self, message: str, session_id: str = "desktop",
                    *, on_chunk=None) -> str:
        """Stream the reply; calls ``on_chunk(text)`` per chunk as it arrives.

        Returns the full reply. Uses plain chunked HTTP (``/chat/stream``), so
        it works with the standard library alone.
        """
        url = f"{self.base_url}/chat/stream"
        data = json.dumps({"message": message,
                        "session_id": session_id}).encode()
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        parts: list[str] = []
        try:
            # Scheme validated to http/https in __init__ (no file:/ SSRF).
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:  # noqa: S310  # nosec B310
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    parts.append(text)
                    if on_chunk is not None:
                        on_chunk(text)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                payload = json.loads(exc.read() or b"{}")
                detail = str(payload.get("detail", ""))
            except (json.JSONDecodeError, OSError):
                pass
            raise ApiError(exc.code, detail or f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(0, f"Cannot reach server: {exc.reason}") from exc
        return "".join(parts)
