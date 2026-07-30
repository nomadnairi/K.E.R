"""
The hosted LLM proxy — "API от меня".

A Pro subscriber should be able to point their own tools at KER and use the
operator's models, without ever being handed a raw provider key they could
copy, share, or run up without limit. This module is that endpoint: an
OpenAI-compatible ``POST /v1/chat/completions`` (plus ``GET /v1/models``) that

1. authenticates the caller by a long-lived **API key** (``ker-…``) or a login
   token,
2. refuses anyone whose tier does not include ``api_access``,
3. meters the request against that tier's daily token allowance (Pro is
   unlimited), and
4. forwards it to the operator's providers through the engine's own
   :class:`~jarvis.llm.client.LLMClient`, then books what it cost.

Because every call is checked against a live account, revocation is immediate:
revoke the key, deactivate the account, or downgrade the licence, and the very
next request is refused. The key management routes (create / list / revoke) live
here too, since they exist only to serve this endpoint.

The wire shape is a deliberate subset of OpenAI's, so existing clients and SDKs
work by only changing the base URL and key.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel

from jarvis.billing.metering import UsageMeter, quotas_from_settings
from jarvis.config.settings import Settings
from jarvis.core.engine import JarvisEngine
from jarvis.licensing import LicenseService
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


# Defined at module scope, not inside install_proxy_routes: with
# ``from __future__ import annotations`` the route annotations are strings, and
# FastAPI resolves them against module globals — a model hidden in a function's
# locals would be misread as a query parameter.
class ProxyMessage(BaseModel):
    role: str
    content: object = ""


class ChatCompletionIn(BaseModel):
    model: str = ""
    messages: list[ProxyMessage] = []
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = None


def estimate_tokens(text: str) -> int:
    """Rough token count for metering when a provider reports none.

    Streaming gives text but not always a token tally, so a soft quota needs an
    estimate rather than a free pass. ~4 characters per token is the usual
    English/Russian rule of thumb; deliberately an over-estimate on short text
    (min 1) so a stream is never counted as zero.
    """
    return max(1, len(text) // 4)


def split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Pull ``system`` turns out of an OpenAI-style message list.

    Providers take the system prompt as a separate argument (Anthropic requires
    it), so fold any system messages into one string and hand back the rest as
    user/assistant turns.
    """
    system_parts: list[str] = []
    rest: list[dict] = []
    for msg in messages:
        role = str(msg.get("role", "")).strip()
        content = msg.get("content", "")
        if isinstance(content, list):
            # OpenAI content-parts array → keep only the text parts.
            content = "".join(
                part.get("text", "") for part in content
                if isinstance(part, dict) and part.get("type") == "text")
        content = str(content)
        if role == "system":
            if content:
                system_parts.append(content)
        elif role in ("user", "assistant"):
            rest.append({"role": role, "content": content})
    return "\n\n".join(system_parts), rest


def resolve_route(model: str, profiles: list[str]) -> tuple[str | None, str | None]:
    """Map a requested model to (profile, model-override) for the LLM client.

    - a profile name ("claude", "gpt", "openrouter", "local") pins that provider;
    - a ``vendor/model`` id routes through OpenRouter when it is configured;
    - anything else is passed as a model override on the default chain.
    """
    model = (model or "").strip()
    if model and model in profiles:
        return model, None
    if "/" in model and "openrouter" in profiles:
        return "openrouter", model
    return None, (model or None)


def install_proxy_routes(app, settings: Settings, service: LicenseService,
                         engine: JarvisEngine) -> None:
    """Register ``/v1/*`` and the API-key routes on *app*."""
    from fastapi import APIRouter, Depends, Header, HTTPException
    from fastapi.responses import StreamingResponse

    from jarvis.api.auth import active_tier
    from jarvis.billing import PRO
    from jarvis.billing.entitlements import API_ACCESS, features_for
    from jarvis.interfaces.usage import UsageStore

    router = APIRouter()

    # One ledger + meter for the whole process. Kept on app.state so it lives as
    # long as the app and is reachable for a clean close in tests.
    store = UsageStore(settings.memory_db_path)
    meter = UsageMeter(store, quotas_from_settings(settings))
    app.state.proxy_store = store

    def _account_and_tier(key: str | None):
        """Resolve a caller to (account, tier, owner) or ``None``.

        An API key wins over a login token; both map to the same account.
        """
        if not key:
            return None
        account = service.validate_api_key(key) or service.validate_token(key)
        if account is None:
            return None
        owner = bool(settings.owner_username
                     and account.username.lower()
                     == settings.owner_username.lower())
        tier = PRO if owner else active_tier(account, service)
        return account, tier, owner

    def _entitled_caller(authorization: str | None, x_api_key: str | None):
        """Resolve → (principal, tier, owner) past auth + entitlement.

        This is the shared gate: a live account that is allowed to touch the
        proxy at all. The daily-quota check is layered on top for the endpoints
        that actually spend tokens; the usage endpoint deliberately skips it so
        it can still report an account that is already over its limit.
        """
        key = None
        if authorization and authorization.startswith("Bearer "):
            key = authorization[len("Bearer "):]
        key = key or x_api_key
        resolved = _account_and_tier(key)
        if resolved is None:
            raise HTTPException(status_code=401,
                                detail="Invalid or missing API key.")
        account, tier, owner = resolved
        if API_ACCESS not in features_for(tier, owner=owner):
            raise HTTPException(
                status_code=403,
                detail="Your plan does not include API access. Upgrade to Plus "
                        "or Pro to use the API.")
        return f"user:{account.username}", tier, owner

    async def proxy_caller(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ):
        """The account behind a proxy call, past auth + entitlement + meter."""
        principal, tier, owner = _entitled_caller(authorization, x_api_key)
        decision = meter.check(principal, tier)
        if not decision.allowed:
            raise HTTPException(
                status_code=429,
                detail=(f"Daily API token limit reached "
                        f"({decision.limit} tokens). It resets in 24 hours, or "
                        f"upgrade for a higher allowance."),
                headers={"Retry-After": "3600"})
        return principal, tier, owner

    # -- OpenAI-compatible surface -------------------------------------------

    @router.get("/v1/models")
    async def list_models(caller=Depends(proxy_caller)) -> dict:
        """The models this server exposes, in OpenAI's list shape."""
        now = int(time.time())
        data = [{"id": name, "object": "model", "created": now, "owned_by": "ker"}
                for name in engine.llm.list_profiles()]
        return {"object": "list", "data": data}

    @router.get("/v1/usage")
    async def usage(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> dict:
        """Today's proxy token spend for the caller, against the tier ceiling.

        Reports even an account that is over its limit, so a client can show
        "used up" rather than only ever getting a 429.
        """
        principal, tier, _owner = _entitled_caller(authorization, x_api_key)
        snap = meter.snapshot(principal, tier)
        return {"tier": tier, **snap.as_dict()}

    def _cap_output(requested: int | None) -> int | None:
        ceiling = settings.proxy_max_output_tokens
        if ceiling <= 0:
            return requested
        if requested is None or requested > ceiling:
            return ceiling
        return requested

    @router.post("/v1/chat/completions")
    async def chat_completions(body: ChatCompletionIn,
                               caller=Depends(proxy_caller)):
        principal, _tier, _owner = caller
        system, messages = split_system([m.model_dump() for m in body.messages])
        if not messages:
            raise HTTPException(status_code=400,
                                detail="At least one user message is required.")
        profile, model_override = resolve_route(
            body.model, engine.llm.list_profiles())
        _cap_output(body.max_tokens)  # reserved: providers honour their own cap
        created = int(time.time())
        cid = "chatcmpl-" + uuid.uuid4().hex[:24]
        model_label = body.model or profile or "ker"

        if body.stream:
            return StreamingResponse(
                _stream(principal, cid, created, model_label,
                        messages, system, profile, model_override),
                media_type="text/event-stream")

        try:
            result = await engine.llm.complete(
                messages, system=system or None,
                profile=profile, model=model_override)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            logger.warning("Proxy completion failed: %s", exc)
            raise HTTPException(status_code=502,
                                detail="Upstream model error.") from exc

        prompt_tokens = result.input_tokens or estimate_tokens(
            system + " ".join(m["content"] for m in messages))
        completion_tokens = result.output_tokens or estimate_tokens(result.text)
        meter.record(principal, prompt_tokens + completion_tokens)
        return {
            "id": cid, "object": "chat.completion", "created": created,
            "model": result.model or model_label,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.text},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    async def _stream(principal, cid, created, model_label,
                      messages, system, profile, model_override):
        import json

        def frame(delta: dict, finish=None) -> str:
            payload = {
                "id": cid, "object": "chat.completion.chunk",
                "created": created, "model": model_label,
                "choices": [{"index": 0, "delta": delta,
                            "finish_reason": finish}],
            }
            return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        yield frame({"role": "assistant"})
        collected: list[str] = []
        try:
            async for chunk in engine.llm.stream(
                    messages, system=system or None,
                    profile=profile, model=model_override):
                collected.append(chunk)
                yield frame({"content": chunk})
        except Exception as exc:  # noqa: BLE001 - end the stream cleanly
            logger.warning("Proxy stream failed: %s", exc)
            yield frame({"content": f"\n[error: {exc}]"}, finish="stop")
            yield "data: [DONE]\n\n"
            return
        # Best-effort metering: providers rarely tally tokens mid-stream.
        spent = estimate_tokens(
            system + " ".join(m["content"] for m in messages)) \
            + estimate_tokens("".join(collected))
        meter.record(principal, spent)
        yield frame({}, finish="stop")
        yield "data: [DONE]\n\n"

    app.include_router(router)
