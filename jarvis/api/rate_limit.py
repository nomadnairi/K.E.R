"""
Per-IP rate limiting for brute-forceable HTTP endpoints.

Applied once as ASGI middleware rather than sprinkled into individual route
handlers — one place to see every throttled route, one place to change a
limit. Before this, none of ``/auth/login``, ``/auth/register`` or
``/auth/telegram`` had any throttling at all: a password, or a bot-issued
6-digit Telegram login code (1,000,000 possibilities, live for its full
10-minute TTL), could be guessed at whatever rate the network allowed.

Reuses the token-bucket primitive already used for per-session chat
throttling (:class:`jarvis.core.ratelimit.RateLimiter`); the two are
otherwise unrelated call sites (this one keys by client IP across a fixed
set of routes, that one keys by chat session) and are not unified further —
chat traffic already has its own limiter in the engine pipeline, and the
hosted proxy meters its own daily token budget. Duplicating either here
would just be two limiters disagreeing with each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from jarvis.core.ratelimit import RateLimiter


@dataclass(frozen=True)
class RouteLimit:
    """One throttled route: an exact method + path, with its own bucket."""

    method: str
    path: str
    capacity: int
    window_seconds: float


def default_limits(capacity: int, window_seconds: float) -> tuple[RouteLimit, ...]:
    """The endpoints brute-forcing or spamming actually pays off on.

    Login and registration are guessable-credential attacks; the Telegram
    code exchange and the dashboard's cookie-session equivalent both redeem a
    6-digit code from a fixed, small space within a 10-minute window.
    """
    return (
        RouteLimit("POST", "/auth/login", capacity, window_seconds),
        RouteLimit("POST", "/auth/register", capacity, window_seconds),
        RouteLimit("POST", "/auth/telegram", capacity, window_seconds),
        RouteLimit("POST", "/auth/web/session", capacity, window_seconds),
        # Re-checks the current password (Этап 2 / Фаза B5) — a stolen
        # bearer token alone should not buy an attacker unlimited guesses
        # at the real password behind it.
        RouteLimit("POST", "/auth/change-password", capacity, window_seconds),
    )


def client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    """The caller's address for rate-limiting purposes.

    Defaults to the raw socket peer. Trusting ``X-Forwarded-For`` by default
    would let any caller pick its own bucket — or someone else's — simply by
    sending the header itself; it is only honoured when the operator has
    confirmed the API sits behind a reverse proxy that sets it (see
    ``Settings.api_trust_proxy_headers`` and ``deploy/nginx``).
    """
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # The proxy appends the peer it received the request from; with
            # exactly one trusted hop in front of this process, the first
            # entry is the address that connected to it.
            return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


class SensitiveRouteRateLimit(BaseHTTPMiddleware):
    """Throttles a fixed set of sensitive routes, per client IP.

    Every other route is untouched by this middleware.
    """

    def __init__(self, app: ASGIApp, *, limits: tuple[RouteLimit, ...],
                trust_proxy_headers: bool = False) -> None:
        super().__init__(app)
        self._trust_proxy_headers = trust_proxy_headers
        self._limiters: dict[tuple[str, str], RateLimiter] = {
            (rule.method, rule.path): RateLimiter(
                capacity=rule.capacity, window_seconds=rule.window_seconds)
            for rule in limits
        }

    async def dispatch(self, request: Request, call_next):
        limiter = self._limiters.get((request.method, request.url.path))
        if limiter is not None:
            ip = client_ip(request, trust_proxy_headers=self._trust_proxy_headers)
            if not limiter.allow(ip):
                return JSONResponse(
                    {"detail": "Too many requests. Try again in a minute."},
                    status_code=429,
                    headers={"Retry-After": str(int(limiter.window_seconds))},
                )
        return await call_next(request)
