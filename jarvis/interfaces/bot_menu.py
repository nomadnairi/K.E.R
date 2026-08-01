"""
Inline-menu content for the Telegram bot (aiogram-free, testable).

The bot is fully button-driven — users never type commands. Every screen is
returned here as ``(text, rows)`` where ``rows`` is a list of button rows and
each button is a ``(label, callback_data)`` pair. The bot layer turns rows into
an ``InlineKeyboardMarkup`` and edits the same message in place, so navigating
feels like a little app.

Callback scheme (kept short — Telegram caps callback_data at 64 bytes):
    m:main  m:profile  m:usage  m:subscription  m:settings  m:memory
    m:model  m:language  m:help  m:link  m:plans  m:reset  m:forget  m:admin
    m:setmodel:<name|auto>   m:setlang:<locale>   m:buy[:<tier>]
    m:catalog[:<page>]   m:setcat:<index>   m:plandetail:<tier>
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from jarvis.i18n import t

CB = "m"

Rows = list[list[tuple[str, str]]]

# AI-picker labels.
MODEL_LABELS = {
    "claude": "🧠 Claude", "gpt": "💬 ChatGPT", "openrouter": "🌐 OpenRouter",
    "local": "🖥 Local", "auto": "⚙️ Auto",
}
LANG_LABELS = {"en": "🇬🇧 English", "ru": "🇷🇺 Русский", "uz": "🇺🇿 O'zbek"}


def _b(label: str, action: str) -> tuple[str, str]:
    return (label, f"{CB}:{action}")


def _nav(locale: str, back: str = "main") -> list[tuple[str, str]]:
    """Universal navigation row: ⬅️ Back · 🏠 Home · ❌ Close.

    ``back`` is the parent screen's bare action name. For a top-level screen
    (``back == "main"``) Home is redundant with Back, so only ⬅️/❌ are shown.
    """
    close = _b(t("menu_close", locale), "close")
    if back == "main":
        return [_b(t("menu_back", locale), "main"), close]
    return [_b(t("menu_back", locale), back),
            _b(t("menu_home", locale), "main"), close]


def _back(locale: str, parent: str = "main") -> list[tuple[str, str]]:
    return _nav(locale, parent)


def card_rows(locale: str, refresh_action: str) -> Rows:
    """Buttons for an info card: a Refresh (re-open the same screen) + nav row.

    ``refresh_action`` is a bare action name (e.g. ``"profile"``); the ``m:``
    prefix is added here.
    """
    return [
        [_b(t("menu_refresh", locale), refresh_action)],
        _nav(locale, "main"),
    ]


def _fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _yn(value: bool) -> str:
    return "✅" if value else "❌"


# -- screens ------------------------------------------------------------------

def plan_status(locale: str, plan, used_today: int) -> str:
    """One-line tier badge for the main menu (e.g. '🆓 Free · 7/10 today')."""
    name = t(f"plan_{plan.name}", locale)
    if plan.unlimited:
        tail = t("plan_unlimited", locale)
    else:
        tail = t("plan_left_today", locale,
                n=plan.remaining_daily(used_today), total=plan.daily_messages)
    return f"{plan.emoji} <b>{name}</b> · {tail}"


def screen_main(locale: str, *, is_admin: bool = False, billing_on: bool = False,
                accounts_on: bool = False, multi_model: bool = False,
                voice_on: bool = False, channel: str = "", name: str = "Sir",
                plan=None, used_today: int = 0,
                image_on: bool = False, referral_on: bool = False,
                integrations_on: bool = False, assistant_name: str = "KER",
                ) -> tuple[str, Rows]:
    header = (
        f"🤖 <b>{assistant_name}</b>\n"
        f"<i>{t('menu_greeting', locale, name=name)}</i>"
    )
    if plan is not None:
        header += f"\n{plan_status(locale, plan, used_today)}"
    text = f"{header}\n\n{t('menu_pick', locale)}"
    rows: Rows = [
        [_b(t("menu_profile", locale), "profile"),
        _b(t("menu_usage", locale), "usage")],
        [_b(t("menu_settings", locale), "settings"),
        _b(t("menu_memory", locale), "memory")],
        [_b(t("menu_ideas", locale), "ideas"),
        _b(t("menu_newchat", locale), "newchat")],
        [_b(t("menu_reminders", locale), "reminders"),
        _b(t("menu_automations", locale), "automations")],
    ]
    third = [_b(t("menu_language", locale), "language")]
    if voice_on:
        third.insert(0, _b(t("menu_voice", locale), "voice"))
    if image_on:
        third.insert(0, _b(t("menu_image", locale), "image"))
    rows.append(third)
    if billing_on:
        rows.append([_b(t("menu_plans", locale), "plans"),
                    _b(t("menu_subscription", locale), "subscription")])
    if integrations_on:
        rows.append([_b(t("menu_integrations", locale), "myint")])
    if referral_on:
        rows.append([_b(t("menu_referral", locale), "referral")])
    if accounts_on:
        rows.append([_b(t("menu_link", locale), "link")])
    rows.append([_b(t("menu_help", locale), "help"),
                _b(t("menu_support", locale), "support")])
    last = [_b(t("menu_about", locale), "about")]
    if channel:
        last.append((t("menu_channel", locale), channel_url(channel)))
    rows.append(last)
    if is_admin:
        rows.append([_b(t("menu_admin", locale), "admin")])
    return text, rows


def plan_card(locale: str, plan, *, current: bool = False) -> str:
    """A comparison block for one tier, used inside the Tariffs screen."""
    head = f"{plan.emoji} <b>{t(f'plan_{plan.name}', locale)}</b>"
    if plan.price_stars:
        head += f" — ⭐{plan.price_stars}"
    if current:
        head += f"  · {t('plan_current', locale)}"
    daily = (t("plan_unlimited", locale) if plan.unlimited
            else t("plan_per_day", locale, n=plan.daily_messages))
    models = (t("plan_models_all", locale) if plan.all_models
            else t("plan_models_basic", locale))
    integrations = (t("plan_unlimited", locale) if plan.unlimited_integrations
                    else str(plan.integrations))
    return "\n".join([
        head,
        f"   💬 {daily}",
        f"   🧠 {models}",
        f"   🔗 {t('plan_feat_integrations', locale)}: {integrations}",
        f"   🎨 {t('plan_feat_images', locale)}: {_yn(plan.images)}",
        f"   🔌 {t('plan_feat_api', locale)}: {_yn(plan.api_access)}",
        f"   🛟 {t('plan_feat_support', locale)}: {t(f'support_{plan.support}', locale)}",
    ])


def screen_plans_hub(locale: str, plans: dict, current_tier: str) -> tuple[str, Rows]:
    """The Tariffs hub — one button per tier, details live one level down."""
    from jarvis.billing import TIER_ORDER

    text = "\n".join([f"💎 <b>{t('plans_title', locale)}</b>", t("plans_hint", locale)])
    rows: Rows = []
    for tier in TIER_ORDER:
        p = plans[tier]
        label = f"{p.emoji} {t(f'plan_{tier}', locale)}"
        if tier == current_tier:
            label += f" · {t('plan_current', locale)}"
        rows.append([_b(label, f"plandetail:{tier}")])
    rows.append(_back(locale))
    return text, rows


def screen_plan_detail(locale: str, plans: dict, current_tier: str,
                        tier: str) -> tuple[str, Rows]:
    """One tier's full card, with a Buy button if it's above the current tier."""
    from jarvis.billing import TIER_ORDER

    plan = plans[tier]
    text = "\n".join([
        f"💎 <b>{t('plans_title', locale)}</b>", "",
        plan_card(locale, plan, current=(tier == current_tier)),
    ])
    rows: Rows = []
    current_rank = TIER_ORDER.index(current_tier) if current_tier in TIER_ORDER else 0
    if tier in ("plus", "pro") and TIER_ORDER.index(tier) > current_rank:
        rows.append([_b(
            t("plan_buy", locale, plan=t(f"plan_{tier}", locale), price=plan.price_stars),
            f"buy:{tier}")])
    rows.append(_nav(locale, "plans"))
    return text, rows


def screen_search(locale: str, results: list, current_slug: str = "",
                ) -> tuple[str, Rows]:
    """Model search results: a picked-from list served through OpenRouter.

    ``results`` is a list of objects with ``slug``, ``name`` and ``free``.
    """
    if not results:
        return (f"🔎 <b>{t('search_title', locale)}</b>\n\n"
                f"{t('search_none', locale)}", [_back(locale)])
    lines = [f"🔎 <b>{t('search_title', locale)}</b>",
            t("search_found", locale, n=len(results)), ""]
    rows: Rows = []
    for i, m in enumerate(results):
        tag = " 🆓" if m.free else ""
        mark = "✅ " if m.slug == current_slug else ""
        lines.append(f"• {m.name}{tag}")
        rows.append([_b(f"{mark}{m.name}{tag}", f"pick:{i}")])
    rows.append(_back(locale))
    return "\n".join(lines), rows


def screen_market_hub(locale: str) -> tuple[str, Rows]:
    """The model marketplace home."""
    text = f"🤖 <b>{t('market_title', locale)}</b>\n\n{t('market_hint', locale)}"
    rows: Rows = [
        [_b(t("market_search", locale), "mktsearch")],
        [_b(t("market_popular", locale), "mktpop"),
        _b(t("market_free", locale), "mktfree")],
        [_b(t("market_top", locale), "mkttop"),
        _b(t("market_favs", locale), "mktfavs")],
        [_b(t("market_cats", locale), "mktcats"),
        _b(t("market_provs", locale), "mktprovs")],
        [_b(t("market_compare", locale), "mktcmp")],
        _back(locale),
    ]
    return text, rows


def screen_market_list(locale: str, title: str, cards: list,
                    current_slug: str = "", fav_slugs=()) -> tuple[str, Rows]:
    """A list of model cards; each opens its full card."""
    import jarvis.interfaces.model_registry as mr

    if not cards:
        return (f"🤖 <b>{title}</b>\n\n{t('market_none', locale)}",
                [_nav(locale, "market")])
    lines = [f"🤖 <b>{title}</b>", t("search_found", locale, n=len(cards)), ""]
    rows: Rows = []
    for c in cards:
        idx = mr.index_of(c.slug)
        mark = ("✅ " if c.slug == current_slug
                else ("⭐ " if c.slug in fav_slugs else ""))
        tag = " 🆓" if c.free else ""
        rows.append([_b(f"{mark}{c.emoji} {c.name}{tag}", f"mktcard:{idx}")])
    rows.append(_nav(locale, "market"))
    return "\n".join(lines), rows


def screen_categories(locale: str) -> tuple[str, Rows]:
    import jarvis.interfaces.model_registry as mr

    text = f"📂 <b>{t('market_cats', locale)}</b>"
    rows: Rows = []
    row: list[tuple[str, str]] = []
    for cid, (emoji, label) in mr.CATEGORIES.items():
        row.append(_b(f"{emoji} {label}", f"mktcat:{cid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_nav(locale, "market"))
    return text, rows


def screen_providers(locale: str) -> tuple[str, Rows]:
    import jarvis.interfaces.model_registry as mr

    text = f"🏢 <b>{t('market_provs', locale)}</b>"
    rows: Rows = []
    row: list[tuple[str, str]] = []
    for pid, name, count in mr.providers_with_models():
        row.append(_b(f"{name} ({count})", f"mktprov:{pid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_nav(locale, "market"))
    return text, rows


def screen_model_card(locale: str, card, *, is_fav: bool = False,
                    can_use: bool = True) -> tuple[str, Rows]:
    import jarvis.interfaces.model_registry as mr

    idx = mr.index_of(card.slug)
    best = ", ".join(card.strengths) or "—"
    lines = [
        f"{card.emoji} <b>{card.name}</b>",
        "━━━━━━━━━━━━━━",
        f"🏢 {t('card_provider', locale)}: <b>{mr.PROVIDERS.get(card.provider, card.provider)}</b>",
        f"📚 {t('card_context', locale)}: <b>{card.context // 1000}K</b>",
        f"🎯 {t('card_best_for', locale)}: {best}",
        f"💵 {t('card_cost', locale)}: {card.cost_label}",
        f"⚡ {t('card_speed', locale)}: {card.stars(card.speed)}",
        f"🏅 {t('card_quality', locale)}: {card.stars(card.quality)}",
        f"🎨 Vision: {_yn(card.vision)}   🔧 Tools: {_yn(card.tools)}",
        f"📦 {t('card_status', locale)}: {card.status}",
    ]
    if card.summary:
        lines += ["", f"<i>{card.summary}</i>"]
    rows: Rows = []
    if can_use:
        rows.append([_b(t("card_use", locale), f"mktuse:{idx}")])
    rows.append([
        _b(t("card_unfav", locale) if is_fav else t("card_fav", locale),
        f"mktfav:{idx}"),
        _b(t("card_compare_add", locale), f"mktcmpadd:{idx}"),
    ])
    rows.append(_nav(locale, "market"))
    return "\n".join(lines), rows


def screen_compare(locale: str, cards: list) -> tuple[str, Rows]:
    import jarvis.interfaces.model_registry as mr

    if not cards:
        return (f"📊 <b>{t('cmp_title', locale)}</b>\n\n{t('cmp_empty', locale)}",
                [_nav(locale, "market")])
    lines = [f"📊 <b>{t('cmp_title', locale)}</b>", ""]
    for c in cards:
        lines.append(f"{c.emoji} <b>{c.name}</b> — {mr.PROVIDERS.get(c.provider, c.provider)}")
        lines.append(f"   📚 {c.context // 1000}K · 💵 {c.cost_label} · "
                    f"⚡{c.stars(c.speed)} · 🏅{c.stars(c.quality)}")
        lines.append(f"   🎨 {_yn(c.vision)}  🔧 {_yn(c.tools)}  "
                    f"🎯 {', '.join(c.strengths[:3])}")
        lines.append("")
    rows: Rows = [[_b(t("cmp_clear", locale), "mktcmpclear")],
                _nav(locale, "market")]
    return "\n".join(lines).strip(), rows


def limit_screen(locale: str, plan) -> tuple[str, Rows]:
    """Shown when a user hits their daily message limit."""
    text = (f"🚦 <b>{t('limit_title', locale)}</b>\n\n"
            f"{t('limit_body', locale, n=plan.daily_messages)}")
    rows: Rows = [[_b(t("menu_plans", locale), "plans")], _back(locale)]
    return text, rows


def referral_link(bot_username: str, user_id: int | str) -> str:
    """The user's personal invite link (`?start=ref_<id>`)."""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def screen_referral(locale: str, *, link: str, count: int,
                    bonus_each: int) -> tuple[str, Rows]:
    """The invite screen: personal link, referral count and earned bonus."""
    from urllib.parse import quote

    total = count * bonus_each
    text = "\n".join([
        f"🎁 <b>{t('ref_title', locale)}</b>",
        "━━━━━━━━━━━━━━",
        t("ref_body", locale, bonus=bonus_each),
        "",
        f"👥 {t('ref_count', locale)}: <b>{count}</b>",
        f"➕ {t('ref_earned', locale)}: <b>+{total}</b> / {t('ref_day', locale)}",
        "",
        f"🔗 <code>{link}</code>",
    ])
    share = (f"https://t.me/share/url?url={quote(link, safe='')}"
            f"&text={quote(t('ref_share_text', locale), safe='')}")
    rows: Rows = [[(t("ref_share", locale), share)], _back(locale)]
    return text, rows


#: Example prompts offered on the Ideas screen (keys resolved per locale).
IDEA_KEYS = ("idea_write", "idea_code", "idea_translate", "idea_plan")


def screen_ideas(locale: str) -> tuple[str, Rows]:
    """A few tappable example prompts to get users started."""
    text = f"💡 <b>{t('ideas_title', locale)}</b>\n\n{t('ideas_hint', locale)}"
    rows: Rows = [[_b(t(key, locale), f"idea:{i}")]
                for i, key in enumerate(IDEA_KEYS)]
    rows.append(_back(locale))
    return text, rows


def screen_support(locale: str) -> tuple[str, Rows]:
    """Prompt the user to write a message that's forwarded to the owner."""
    text = f"💬 <b>{t('support_title', locale)}</b>\n\n{t('support_hint', locale)}"
    rows: Rows = [[_b(t("support_write", locale), "support")], _back(locale)]
    return text, rows


def screen_about(locale: str, *, version: str, voice_on: bool, images_on: bool,
                catalog_on: bool, billing_on: bool) -> tuple[str, Rows]:
    """An About card listing what this deployment has enabled (✅/❌)."""
    feats = [
        (t("about_chat", locale), True),
        (t("about_voice", locale), voice_on),
        (t("about_images", locale), images_on),
        (t("about_catalog", locale), catalog_on),
        (t("about_plans", locale), billing_on),
        (t("about_memory", locale), True),
    ]
    lines = [f"ℹ️ <b>{t('about_title', locale)}</b>",
            f"<i>v{version}</i>", "━━━━━━━━━━━━━━"]
    lines += [f"{_yn(on)} {label}" for label, on in feats]
    return "\n".join(lines), [_back(locale)]


def channel_url(channel: str) -> str:
    """Turn '@name' / 'name' / a full link into a t.me URL (used as a button)."""
    channel = channel.strip()
    if channel.startswith("http"):
        return channel
    return f"https://t.me/{channel.lstrip('@')}"


def screen_voice(locale: str) -> tuple[str, Rows]:
    text = f"🎙 <b>{t('voice_title', locale)}</b>\n\n{t('voice_body', locale)}"
    return text, [_back(locale)]


def gate_screen(locale: str, channel: str) -> tuple[str, Rows]:
    """The subscription gate shown until the user joins the channel."""
    text = f"{t('gate_title', locale)}\n\n{t('gate_body', locale)}"
    rows: Rows = [
        [(t("gate_subscribe", locale), channel_url(channel))],
        [_b(t("gate_check", locale), "checksub")],
    ]
    return text, rows


def screen_settings(locale: str, *, multi_model: bool = False,
                    catalog_on: bool = False,
                    proactive: bool = False,
                    search_on: bool = False,
                    mcp_on: bool = False) -> tuple[str, Rows]:
    """Settings hub — a few category buttons that open focused sub-screens.

    Kept deliberately minimal: individual toggles live one level down inside
    🤖 AI & models, 🌍 Tools & internet and 🎨 Preferences.
    """
    text = f"⚙️ <b>{t('settings_title', locale)}</b>\n\n{t('settings_hint', locale)}"
    rows: Rows = [[_b(t("set_cat_ai", locale), "setai")]]
    if search_on or mcp_on:
        rows.append([_b(t("set_cat_tools", locale), "settools")])
    rows.append([_b(t("set_cat_prefs", locale), "setprefs")])
    rows.append(_back(locale))
    return text, rows


def screen_settings_ai(locale: str, *, multi_model: bool,
                    catalog_on: bool = False) -> tuple[str, Rows]:
    """AI & models sub-hub: catalog, model profile, bring-your-own-key."""
    text = f"🤖 <b>{t('set_cat_ai', locale)}</b>"
    rows: Rows = []
    if catalog_on:
        rows.append([_b(t("menu_catalog", locale), "market")])
    if multi_model:
        rows.append([_b(t("menu_model", locale), "model")])
    rows.append([_b(t("menu_byok", locale), "byok")])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_settings_tools(locale: str, *, search_on: bool,
                        mcp_on: bool) -> tuple[str, Rows]:
    """Tools & internet sub-hub: search providers, MCP servers."""
    text = f"🌍 <b>{t('set_cat_tools', locale)}</b>"
    rows: Rows = []
    if search_on:
        rows.append([_b(t("menu_search_prov", locale), "searchprov")])
    if mcp_on:
        rows.append([_b(t("menu_mcp", locale), "mcp")])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_settings_prefs(locale: str, *, proactive: bool) -> tuple[str, Rows]:
    """Preferences sub-hub: language, proactive messaging."""
    text = f"🎨 <b>{t('set_cat_prefs', locale)}</b>"
    rows: Rows = [
        [_b(t("menu_language", locale), "language")],
        [_b(t("menu_rename", locale), "renamea")],
        [_b(f"{t('menu_proactive', locale)}: {_yn(proactive)}", "proactive")],
        _nav(locale, "settings"),
    ]
    return text, rows


def screen_user_integrations(locale: str, items: list[tuple[int, str]],
                            count: int, limit: str,
                            at_limit: bool) -> tuple[str, Rows]:
    """A user's own integrations with a tier-gated add limit."""
    head = (f"🔗 <b>{t('uint_title', locale)}</b>\n"
            f"{t('uint_count', locale, n=count, limit=limit)}\n\n"
            f"{t('uint_hint', locale)}")
    lines = [head]
    rows: Rows = []
    for iid, label in items:
        lines.append(f"• {label}")
        rows.append([_b(f"🗑 {label[:36]}", f"intdel:{iid}")])
    if at_limit:
        lines += ["", f"🔒 {t('uint_limit', locale)}"]
        rows.append([_b(t("menu_plans", locale), "plans")])
    else:
        rows.append([_b(t("uint_add_ha", locale), "intadd:homeassistant"),
                    _b(t("uint_add_hook", locale), "intadd:webhook")])
    rows.append(_back(locale))
    return "\n".join(lines), rows


def screen_automations(locale: str,
                    items: list[tuple[int, str]]) -> tuple[str, Rows]:
    """Active recurring automations with cancel buttons."""
    head = f"🔁 <b>{t('auto_title', locale)}</b>\n\n{t('auto_hint', locale)}"
    if not items:
        return f"{head}\n\n{t('auto_empty', locale)}", [_back(locale)]
    lines = [head, ""]
    rows: Rows = []
    for aid, label in items:
        lines.append(f"• {label}")
        rows.append([_b(f"🗑 {label[:40]}", f"autocancel:{aid}")])
    rows.append(_back(locale))
    return "\n".join(lines), rows


def screen_reminders(locale: str, items: list[tuple[int, str]]) -> tuple[str, Rows]:
    """Active reminders (``items`` = ``(id, label)``) with cancel buttons."""
    head = f"⏰ <b>{t('reminders_title', locale)}</b>\n\n{t('reminders_hint', locale)}"
    if not items:
        return f"{head}\n\n{t('reminders_empty', locale)}", [_back(locale)]
    lines = [head, ""]
    rows: Rows = []
    for rid, label in items:
        lines.append(f"• {label}")
        rows.append([_b(f"🗑 {label[:40]}", f"remcancel:{rid}")])
    rows.append(_back(locale))
    return "\n".join(lines), rows


BYOK_PROVIDERS = (("openai", "🔷 OpenAI"), ("openrouter", "🌐 OpenRouter"),
                ("anthropic", "🧠 Anthropic"))


def screen_byok(locale: str, current_provider: str | None = None) -> tuple[str, Rows]:
    """Bring-your-own-key: connect a personal provider key (removes limits)."""
    status = (t("byok_active", locale, provider=current_provider)
            if current_provider else t("byok_none", locale))
    text = (f"🔑 <b>{t('byok_title', locale)}</b>\n\n"
            f"{t('byok_hint', locale)}\n\n{status}")
    rows: Rows = []
    for prov, label in BYOK_PROVIDERS:
        mark = "✅ " if prov == current_provider else ""
        rows.append([_b(mark + label, f"byokset:{prov}")])
    if current_provider:
        rows.append([_b(t("byok_disconnect", locale), "byokoff")])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_catalog(locale: str, user_tier: str, current_slug: str,
                page: int = 0) -> tuple[str, Rows]:
    """A paginated, tier-gated catalog of models (served via OpenRouter)."""
    from jarvis.interfaces import model_catalog as mc

    text = (f"🗂 <b>{t('catalog_title', locale)}</b>\n\n"
            f"{t('catalog_hint', locale)}")
    rows: Rows = []
    for idx, model in mc.page(page):
        locked = not mc.unlocked(model, user_tier)
        mark = "✅ " if model.slug == current_slug else ("🔒 " if locked else "")
        label = f"{mark}{model.emoji} {model.name}"
        if model.note:
            label += f" · {model.note}"
        rows.append([_b(label, f"setcat:{idx}")])
    pages = mc.page_count()
    if pages > 1:
        rows.append([
            _b("◀️", f"catalog:{(page - 1) % pages}"),
            _b(f"{page + 1}/{pages}", f"catalog:{page}"),
            _b("▶️", f"catalog:{(page + 1) % pages}"),
        ])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_search_providers(locale: str, statuses, active: str | None,
                            ) -> tuple[str, Rows]:
    """Read-only view of the Search Provider Manager: providers by category,
    each marked available (✅) or needs-a-key (❌), with the active one starred.
    """
    from jarvis.search.manager import KIND_LABELS

    lines = [f"🌍 <b>{t('search_prov_title', locale)}</b>",
            t("search_prov_hint", locale), ""]
    by_kind: dict[str, list] = {}
    for st in statuses:
        by_kind.setdefault(st.kind, []).append(st)
    for kind in ("ai", "web", "browser"):
        group = by_kind.get(kind)
        if not group:
            continue
        lines.append(f"<b>{KIND_LABELS.get(kind, kind)}</b>")
        for st in group:
            mark = "⭐ " if st.name == active else ""
            key = "" if not st.requires_key else (
                " 🔑" if not st.available else "")
            lines.append(f"   {mark}{_yn(st.available)} {st.label}{key}")
        lines.append("")
    return "\n".join(lines).strip(), [_nav(locale, "settings")]


def screen_mcp(locale: str, statuses, tool_names) -> tuple[str, Rows]:
    """Read-only view of MCP servers and the tools they mounted.

    ``statuses`` are objects with ``name``, ``connected``, ``tool_count`` and
    ``detail``; ``tool_names`` is a flat list of mounted tool skill names.
    """
    lines = [f"🧩 <b>{t('mcp_title', locale)}</b>", t("mcp_hint", locale), ""]
    if not statuses:
        lines.append(t("mcp_none", locale))
        return "\n".join(lines), [_nav(locale, "settings")]
    for st in statuses:
        head = f"{_yn(st.connected)} <b>{st.name}</b> · {st.tool_count} 🔧"
        if not st.connected and st.detail:
            head += f"\n   <i>{st.detail[:80]}</i>"
        lines.append(head)
    if tool_names:
        lines += ["", f"<b>{t('mcp_tools', locale)}</b>"]
        lines += [f"   • <code>{n}</code>" for n in tool_names[:20]]
    return "\n".join(lines).strip(), [_nav(locale, "settings")]


def screen_memory(locale: str) -> tuple[str, Rows]:
    text = f"🧠 <b>{t('memory_title', locale)}</b>\n\n{t('memory_hint', locale)}"
    rows: Rows = [
        [_b(t("menu_reset", locale), "reset")],
        [_b(t("menu_forget", locale), "forget")],
        _back(locale),
    ]
    return text, rows


def screen_confirm(locale: str, kind: str) -> tuple[str, Rows]:
    """Confirmation step for a destructive action ('reset' or 'forget')."""
    text = f"⚠️ <b>{t('confirm_title', locale)}</b>\n\n{t(f'confirm_{kind}', locale)}"
    rows: Rows = [
        [_b(t("confirm_yes", locale), f"{kind}_do")],
        [_b(t("menu_back", locale), "memory")],
    ]
    return text, rows


def screen_admin(locale: str, *, billing_on: bool = False) -> tuple[str, Rows]:
    """Owner admin hub — opens the full panel and the sales report inline."""
    text = f"🛠 <b>{t('admin_title', locale)}</b>\n\n{t('admin_hint', locale)}"
    rows: Rows = [[_b(t("admin_open_panel", locale), "adminpanel")]]
    if billing_on:
        rows.append([_b(t("admin_open_sales", locale), "adminsales")])
    rows.append(_back(locale))
    return text, rows


def screen_model(locale: str, profiles: list[str], current: str) -> tuple[str, Rows]:
    text = f"🤖 <b>{t('menu_model', locale)}</b>\n\n{t('model_choose', locale)}"
    rows: Rows = []
    for name in profiles:
        mark = "✅ " if name == current else ""
        rows.append([_b(mark + MODEL_LABELS.get(name, name), f"setmodel:{name}")])
    mark = "✅ " if not current else ""
    rows.append([_b(mark + MODEL_LABELS["auto"], "setmodel:auto")])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_language(locale: str, current: str) -> tuple[str, Rows]:
    text = f"🌐 <b>{t('menu_language', locale)}</b>\n\n{t('choose_language', locale)}"
    rows: Rows = []
    for loc, label in LANG_LABELS.items():
        mark = "✅ " if loc == current else ""
        rows.append([_b(mark + label, f"setlang:{loc}")])
    rows.append(_nav(locale, "settings"))
    return text, rows


def screen_help(locale: str) -> tuple[str, Rows]:
    text = f"❓ <b>{t('help_title', locale)}</b>\n\n{t('help_body', locale)}"
    return text, [_back(locale)]


def screen_link(locale: str, *, app_login: bool = False) -> tuple[str, Rows]:
    text = f"🔗 <b>{t('menu_link', locale)}</b>\n\n{t('link_usage', locale)}"
    rows: Rows = []
    if app_login:
        rows.append([_b(t("app_login_btn", locale), "appcode")])
    rows.append(_back(locale))
    return text, rows


# -- info cards (text only; the bot appends a Back button) --------------------

def profile_text(locale: str, *, telegram_id: int, name: str, language: str,
                model: str, account: str | None, telegram_verified: bool,
                stats: dict, plan_label: str | None = None,
                voice_on: bool | None = None, images_on: bool | None = None,
                own_key: str | None = None) -> str:
    model_label = MODEL_LABELS.get(model, model) if model else "⚙️ Auto"
    account_line = (f"🔓 <b>{account}</b>" if account
                    else t("profile_no_account", locale))
    verified = "✅" if telegram_verified else "—"
    lang_label = LANG_LABELS.get(language, language)
    lines = [
        f"👤 <b>{t('profile_title', locale)}</b>",
        "━━━━━━━━━━━━━━",
        f"🆔 <code>{telegram_id}</code>",
        f"📛 {t('profile_name', locale)}: <b>{name}</b>",
        f"🔗 {t('profile_account', locale)}: {account_line}",
        f"✔️ {t('profile_verified', locale)}: {verified}",
        f"🌐 {t('profile_language', locale)}: {lang_label}",
        f"🤖 {t('profile_model', locale)}: {model_label}",
    ]
    if plan_label is not None:
        lines.append(f"💎 {t('profile_plan', locale)}: <b>{plan_label}</b>")
    # Feature status with ✅/❌.
    status = []
    if voice_on is not None:
        status.append(f"🎙 {t('profile_voice', locale)} {_yn(voice_on)}")
    if images_on is not None:
        status.append(f"🎨 {t('profile_images', locale)} {_yn(images_on)}")
    if own_key is not None:
        status.append(f"🔑 {t('profile_ownkey', locale)} "
                    f"{('✅ ' + own_key) if own_key else '❌'}")
    if status:
        lines += ["━━━━━━━━━━━━━━", "   ".join(status)]
    lines += [
        "━━━━━━━━━━━━━━",
        f"💬 {t('profile_messages', locale)}: <b>{_fmt_num(stats['messages'])}</b>",
        f"🔢 {t('profile_tokens', locale)}: <b>{_fmt_num(stats['tokens'])}</b>",
    ]
    return "\n".join(lines)


def usage_text(locale: str, stats: dict) -> str:
    tok = t("usage_tokens", locale)
    return "\n".join([
        f"📊 <b>{t('usage_title', locale)}</b>",
        "━━━━━━━━━━━━━━",
        f"📅 {t('usage_today', locale)}",
        f"    💬 {_fmt_num(stats['messages_today'])}   "
        f"🔢 {_fmt_num(stats['tokens_today'])} {tok}",
        "",
        f"🗓 {t('usage_month', locale)}",
        f"    💬 {_fmt_num(stats['messages_month'])}   "
        f"🔢 {_fmt_num(stats['tokens_month'])} {tok}",
        "",
        f"♾ {t('usage_all', locale)}",
        f"    💬 {_fmt_num(stats['messages'])}   "
        f"🔢 {_fmt_num(stats['tokens'])} {tok}",
    ])


def subscription_text(locale: str, *, account: str | None, licenses: list,
                    now: float | None = None) -> str:
    now = time.time() if now is None else now
    if account is None:
        return "\n".join([f"💳 <b>{t('sub_title', locale)}</b>",
                        "━━━━━━━━━━━━━━", t("sub_none", locale)])
    active = next((lic for lic in licenses if lic.is_valid(now=now)), None)
    lines = [f"💳 <b>{t('sub_title', locale)}</b>", "━━━━━━━━━━━━━━",
            f"🔓 {t('profile_account', locale)}: <b>{account}</b>"]
    if active is None:
        lines.append(f"⚠️ {t('sub_inactive', locale)}")
    else:
        lines.append(f"✅ {t('sub_active', locale)}: <b>{active.plan}</b>")
        if active.expires_at is None:
            lines.append(f"♾ {t('sub_perpetual', locale)}")
        else:
            days = max(0, int((active.expires_at - now) // 86400))
            until = datetime.fromtimestamp(
                active.expires_at, tz=timezone.utc).strftime("%d.%m.%Y")
            lines.append(f"⏳ {t('sub_until', locale)}: <b>{until}</b> "
                        f"({days} {t('sub_days', locale)})")
    return "\n".join(lines)
