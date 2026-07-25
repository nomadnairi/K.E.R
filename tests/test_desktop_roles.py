"""Owner (admin) vs signed-in guest (user) desktop tab visibility."""

from __future__ import annotations

from jarvis.desktop_app.app import visible_tabs


def test_admin_sees_config_panels():
    tabs = visible_tabs("admin")
    for t in ("deck", "assistant", "general", "capabilities", "integrations", "logs"):
        assert t in tabs
    # Command Deck is first — it is the app's main screen.
    assert tabs[0] == "deck"


def test_user_gets_the_deck_only():
    """A guest sees one window: the Command Deck, no native config panels."""
    assert visible_tabs("user") == ("deck",)
    for hidden in ("general", "capabilities", "integrations", "logs", "assistant"):
        assert hidden not in visible_tabs("user")


def test_no_duplicated_native_screens():
    """Chat / voice / memory live in the deck, so no native tab duplicates them."""
    for role in ("admin", "user"):
        for dup in ("chat", "voice", "memory"):
            assert dup not in visible_tabs(role)


def test_config_defaults_to_admin():
    from jarvis.desktop_app.config import AppConfig
    assert AppConfig().role == "admin"
