"""What the desktop app puts in its window.

The app is one window filled by the interface. The native panels only appear in
a build without a web view, where there would otherwise be nothing to show —
and even then a signed-in guest gets fewer of them than the owner.
"""

from __future__ import annotations

from jarvis.desktop_app.app import visible_tabs


def test_the_interface_fills_the_window():
    """With a web view, both roles get the deck and nothing else."""
    for role in ("admin", "user"):
        assert visible_tabs(role) == ("deck",)


def test_fallback_gives_the_owner_the_config_panels():
    """No web view: the owner still needs keys, capabilities and logs."""
    tabs = visible_tabs("admin", webview=False)
    for expected in ("chat", "assistant", "capabilities", "integrations",
                     "general", "logs"):
        assert expected in tabs
    assert "deck" not in tabs, "there is no web view to render the deck in"


def test_fallback_keeps_a_guest_out_of_the_config():
    tabs = visible_tabs("user", webview=False)
    assert tabs == ("chat", "voice")
    for hidden in ("assistant", "capabilities", "integrations", "general",
                   "logs"):
        assert hidden not in tabs


def test_config_defaults_to_admin():
    from jarvis.desktop_app.config import AppConfig
    assert AppConfig().role == "admin"


def test_a_local_owner_is_not_asked_to_sign_in_twice():
    """Choosing local mode is remembered, so the way in is shown once."""
    from jarvis.desktop_app.config import AppConfig
    assert AppConfig().mode_chosen is False
