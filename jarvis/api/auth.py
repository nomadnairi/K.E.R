"""
Authentication wiring for the API.

Two independent mechanisms coexist:

* **Shared key** (``API_KEY``) — a single bearer/``X-API-Key`` secret. Always
  honoured; enough for a private single-user server.
* **Accounts** (``AUTH_ENABLED``) — per-user username/password login backed by
  :class:`~jarvis.licensing.service.LicenseService`. Clients exchange
  credentials for a bearer token at ``POST /auth/login`` and then present it as
  ``Authorization: Bearer <token>``.

This module installs the ``/auth/*`` and ``/admin/*`` routes and exposes helpers
the app uses to resolve the caller's *principal* (a stable string used to
namespace each user's sessions and memory).
"""

import hmac

from jarvis.config.settings import Settings
from jarvis.licensing import AuthError, LicenseService

#: Name of the browser session cookie the web dashboard signs in with.
SESSION_COOKIE = "ker_session"

#: Principal used when the caller authenticated with the shared API key.
SHARED_PRINCIPAL = "shared"


def resolve_principal(
    provided: str | None,
    settings: Settings,
    service: LicenseService | None,
) -> str | None:
    """Map a presented secret to a principal, or ``None`` if unauthorised.

    Order: a valid per-user login token wins; otherwise the shared API key.
    """
    if service is not None and provided:
        account = service.validate_token(provided)
        if account is not None:
            return f"user:{account.username}"
    if not settings.api_key:
        # Open only when no shared key is set AND accounts are not required.
        if service is None:
            return SHARED_PRINCIPAL
    elif provided is not None and hmac.compare_digest(provided, settings.api_key):
        return SHARED_PRINCIPAL
    return None


def plans_for(settings: Settings) -> dict:
    """The tier table for this deployment, with its configured limits."""
    from jarvis.billing import build_plans
    return build_plans(
        free_daily=settings.plan_free_daily,
        plus_daily=settings.plan_plus_daily,
        pro_daily=settings.plan_pro_daily,
        plus_price=settings.plan_plus_price_stars,
        pro_price=settings.plan_pro_price_stars,
    )


def active_tier(account, service: LicenseService | None) -> str:
    """The tier an account is actually on right now.

    An expired or revoked licence is not a tier — anyone without a valid one is
    Free, which is also what a missing licensing service means.
    """
    import time

    from jarvis.billing import FREE, tier_for
    if account is None or service is None:
        return FREE
    valid = next((lic for lic in service.list_licenses(account.id)
                if lic.is_valid(now=time.time())), None)
    return tier_for(valid.plan) if valid else FREE


def profile_for(account, settings: Settings, service: LicenseService | None,
                *, usage=None, owner: bool | None = None) -> dict:
    """Everything a client needs to know about the signed-in person.

    One builder, so the app, the API and any future client cannot disagree
    about what a subscription includes.
    """
    from jarvis.billing import PRO, resolve_plan
    from jarvis.billing.entitlements import (
        LOCAL_ONLY,
        SERVER_ENFORCED,
        describe,
        features_for,
    )

    username = getattr(account, "username", "") or ""
    if owner is None:
        owner = bool(settings.owner_username
                    and username.lower() == settings.owner_username.lower())
    tier = PRO if owner else active_tier(account, service)
    plan = resolve_plan(tier, plans_for(settings))
    features = sorted(features_for(tier, owner=owner))

    used_today = 0
    if usage is not None and username:
        try:
            used_today = int(usage.stats(f"user:{username}")["messages_today"])
        except Exception:  # noqa: BLE001 - usage is a nicety, not a gate
            used_today = 0

    return {
        "username": username,
        "owner": owner,
        "telegram_verified": bool(getattr(account, "telegram_verified", False)),
        "tier": tier,
        "plan": {
            "name": plan.name,
            "emoji": plan.emoji,
            "daily_messages": plan.daily_messages,
            "monthly_messages": plan.monthly_messages,
            "unlimited": plan.unlimited or owner,
            "integrations": plan.integrations,
            "support": plan.support,
            "price_stars": plan.price_stars,
        },
        "usage": {
            "messages_today": used_today,
            "remaining_today": (None if (plan.unlimited or owner)
                                else plan.remaining_daily(used_today)),
        },
        "features": features,
        "capabilities": describe(tier) if not owner else [
            {**row, "included": True} for row in describe(PRO)],
        # So a client can tell a real refusal from a packaging decision.
        "enforced_server_side": sorted(SERVER_ENFORCED),
        "local_only": sorted(LOCAL_ONLY),
    }


def install_auth_routes(app, settings: Settings, service: LicenseService) -> None:
    """Register /auth/* and /admin/* routes on *app*."""
    from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
    from pydantic import BaseModel

    router = APIRouter()

    class LoginIn(BaseModel):
        username: str
        password: str
        # Optional device metadata (Этап 2 / Фаза B1) — a client that sends
        # them lets the account see *what* is logged in (Device Manager);
        # one that doesn't (every pre-existing client) behaves exactly as
        # before, since issue_token() treats them as optional too.
        device_id: str | None = None
        device_name: str = ""
        platform: str = ""
        client_type: str = ""

    class TokenOut(BaseModel):
        token: str
        token_type: str = "bearer"
        expires_in: int

    # /auth/me answers "who am I and what do I get", so the client never has to
    # guess a tier from a plan name.
    class MeOut(BaseModel):
        username: str
        telegram_verified: bool
        owner: bool = False
        tier: str = "free"
        plan: dict = {}
        usage: dict = {}
        features: list[str] = []
        capabilities: list[dict] = []
        enforced_server_side: list[str] = []
        local_only: list[str] = []

    class PairingOut(BaseModel):
        code: str
        expires_in: int

    def _bearer(authorization: str | None, x_api_key: str | None,
                session: str | None = None) -> str | None:
        """The caller's token, from whichever transport it arrived on.

        Three clients, three habits, one kind of token:
        * ``Authorization: Bearer`` — the desktop app and the CLI,
        * ``X-API-Key`` — long-lived keys (headless agents, Raspberry Pi),
        * the ``ker_session`` cookie — the web dashboard.

        The cookie comes last so an explicit header always wins: a browser
        sends its cookie on every request, while a client that bothered to set
        a header meant it.
        """
        if authorization and authorization.startswith("Bearer "):
            return authorization[len("Bearer "):]
        return x_api_key or session

    async def current_account(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
        ker_session: str | None = Cookie(default=None),
    ):
        token = _bearer(authorization, x_api_key, ker_session)
        account = service.validate_token(token) if token else None
        if account is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token.")
        return account

    def _require_admin(x_admin_key: str | None = Header(default=None)) -> None:
        if not settings.auth_admin_key or not x_admin_key or not hmac.compare_digest(
            x_admin_key, settings.auth_admin_key
        ):
            raise HTTPException(status_code=403, detail="Admin key required.")

    # -- user-facing ----------------------------------------------------------

    @router.post("/auth/register", response_model=TokenOut)
    async def register(body: LoginIn) -> TokenOut:
        """Create an account and sign in with it, on the Free tier.

        Off unless the operator turns it on: a deployment that sells only
        through the bot does not want an open registration form. Signing in with
        a Telegram code creates an account too, which is why this is optional
        rather than the only way to get one.
        """
        if not settings.auth_allow_signup:
            raise HTTPException(
                status_code=403,
                detail="Registration is closed on this server — get an "
                        "account through the Telegram bot.")
        username = body.username.strip()
        if len(username) < 3:
            raise HTTPException(status_code=400,
                                detail="The username needs at least 3 characters.")
        if len(body.password) < settings.auth_min_password_length:
            raise HTTPException(
                status_code=400,
                detail=f"The password needs at least "
                        f"{settings.auth_min_password_length} characters.")
        if service.get_account(username) is not None:
            raise HTTPException(status_code=409,
                                detail="That username is taken.")
        try:
            account = service.create_account(username, body.password)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        token = service.issue_token(
            account.id, device_id=body.device_id, device_name=body.device_name,
            platform=body.platform, client_type=body.client_type)
        return TokenOut(token=token,
                        expires_in=settings.auth_token_ttl_hours * 3600)

    @router.post("/auth/login", response_model=TokenOut)
    async def login(body: LoginIn) -> TokenOut:
        try:
            account = service.authenticate(
                body.username, body.password,
                require_license=settings.auth_require_license)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if settings.auth_require_telegram and not account.telegram_verified:
            raise HTTPException(
                status_code=403,
                detail="Link your Telegram account before signing in.",
            )
        token = service.issue_token(
            account.id, device_id=body.device_id, device_name=body.device_name,
            platform=body.platform, client_type=body.client_type)
        return TokenOut(token=token, expires_in=settings.auth_token_ttl_hours * 3600)

    @router.get("/auth/me", response_model=MeOut)
    async def me(account=Depends(current_account)) -> MeOut:
        usage = None
        try:
            from jarvis.interfaces.usage import UsageStore
            usage = UsageStore(settings.memory_db_path)
        except Exception:  # noqa: BLE001 - usage is a nicety, not a gate
            usage = None
        try:
            return MeOut(**profile_for(account, settings, service, usage=usage))
        finally:
            if usage is not None:
                usage.close()

    @router.post("/auth/pairing-code", response_model=PairingOut)
    async def pairing_code(account=Depends(current_account)) -> PairingOut:
        code = service.create_pairing_code(account.id)
        return PairingOut(code=code, expires_in=600)

    class ChangePasswordIn(BaseModel):
        current_password: str
        new_password: str

    @router.post("/auth/change-password")
    async def change_password(body: ChangePasswordIn,
                            account=Depends(current_account)) -> dict:
        """Change the signed-in account's password (Этап 2 / Фаза B5).

        ``change_password()`` on :class:`LicenseService` already existed and
        overwrites blindly — fine for the bot (which just proved control of
        the Telegram account) and the admin CLI (which has the admin key),
        but not for a person who only holds a bearer token: a session left
        open on someone else's machine should not, by itself, be enough to
        take over the account's login entirely. So this path re-checks the
        current password before calling it, the same way changing a password
        on any other account normally works.
        """
        try:
            service.authenticate(account.username, body.current_password)
        except AuthError as exc:
            raise HTTPException(status_code=401,
                                detail="Your current password is incorrect.") from exc
        if len(body.new_password) < settings.auth_min_password_length:
            raise HTTPException(
                status_code=400,
                detail=f"The new password needs at least "
                        f"{settings.auth_min_password_length} characters.")
        service.change_password(account.username, body.new_password)
        return {"status": "changed"}

    # -- API keys (the credential behind the hosted proxy) --------------------
    # Managed here because this is where an account is already resolved. The
    # keys are only useful with the proxy (see jarvis/api/proxy_routes.py), but
    # a person creates and revokes them as part of their account.

    class ApiKeyIn(BaseModel):
        label: str = ""

    @router.get("/auth/api-keys")
    async def list_api_keys(account=Depends(current_account)) -> dict:
        """The account's live API keys — metadata only, never the secret."""
        return {"keys": service.list_api_keys(account.id)}

    @router.post("/auth/api-keys")
    async def create_api_key(body: ApiKeyIn,
                             account=Depends(current_account)) -> dict:
        """Mint a key, returned in plaintext once — only the hash is stored."""
        key = service.create_api_key(account.id, label=body.label)
        return {"key": key, "note": "Store this now — it is shown only once."}

    @router.delete("/auth/api-keys/{key_id}")
    async def revoke_api_key(key_id: int,
                             account=Depends(current_account)) -> dict:
        """Revoke one of the account's keys; effective on the next request."""
        if not service.revoke_api_key(account.id, key_id):
            raise HTTPException(status_code=404, detail="Key not found.")
        return {"status": "revoked", "id": key_id}

    @router.post("/auth/logout")
    async def logout(
        response: Response,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
        ker_session: str | None = Cookie(default=None),
    ) -> dict:
        token = _bearer(authorization, x_api_key, ker_session)
        if token:
            service.revoke_token(token)
        response.delete_cookie(SESSION_COOKIE, path="/",
                            domain=settings.session_cookie_domain or None)
        return {"status": "logged_out"}

    # -- web session ----------------------------------------------------------
    #
    # The dashboard is a separate client from the desktop app, so it gets its
    # own session rather than reusing a desktop token. Same Telegram code
    # mechanism, different vessel: the token goes into an httpOnly cookie the
    # page's JavaScript cannot read, because a token in localStorage is stolen
    # by the first XSS that lands. Signing in on the web neither requires nor
    # invalidates a desktop login.

    class WebLoginIn(BaseModel):
        code: str
        device_id: str | None = None
        device_name: str = ""
        platform: str = ""

    @router.post("/auth/web/session")
    async def open_web_session(body: WebLoginIn, response: Response) -> dict:
        """Exchange a bot-issued code for a browser session cookie."""
        try:
            result = service.redeem_telegram_login(
                body.code, device_id=body.device_id, device_name=body.device_name,
                platform=body.platform, client_type="web")
        except AuthError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid or expired code.")

        token, username = result
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=settings.auth_token_ttl_hours * 3600,
            httponly=True,
            # Secure is dropped only for local development over plain HTTP;
            # in production this rides HTTPS and must stay on.
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
            domain=settings.session_cookie_domain or None,
        )
        return {"username": username}

    @router.get("/auth/web/session")
    async def web_session_state(account=Depends(current_account)) -> dict:
        """Who the browser is signed in as — used on dashboard boot."""
        return {"username": account.username, "authenticated": True}

    # -- admin (operator) -----------------------------------------------------

    class CreateAccountIn(BaseModel):
        username: str
        password: str

    class IssueLicenseIn(BaseModel):
        username: str
        plan: str = "standard"
        valid_days: int | None = None

    @router.post("/admin/accounts")
    async def admin_create_account(
        body: CreateAccountIn, _: None = Depends(_require_admin)
    ) -> dict:
        try:
            account = service.create_account(body.username, body.password)
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"username": account.username, "id": account.id}

    @router.post("/admin/licenses")
    async def admin_issue_license(
        body: IssueLicenseIn, _: None = Depends(_require_admin)
    ) -> dict:
        account = service.get_account(body.username)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        key = service.issue_license(
            account.id, plan=body.plan, valid_days=body.valid_days
        )
        # The plaintext key is returned exactly once — it is stored only hashed.
        return {"username": account.username, "license_key": key, "plan": body.plan}

    app.include_router(router)
