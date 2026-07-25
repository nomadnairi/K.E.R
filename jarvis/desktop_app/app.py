"""
The PySide6 window that hosts the KER interface.

The app is the interface: one window, filled edge to edge by the deck
(``static/desktop.html``), with the sign-in screen
(``static/desktop_login.html``) wearing the same design. Both are served from
the app's own URL scheme and reach back into it through
:mod:`jarvis.desktop_app.bridge`, so every switch in there does real work.

The native Qt panels that remain are the fallback for a build without
QtWebEngine — without a web view there is no interface to render, so the app
puts up plain widgets rather than nothing at all.

Import-safe: PySide6 is imported inside :func:`run_app`, so the rest of the
package (config, API client, engine thread) works without Qt installed.
"""

from __future__ import annotations

from jarvis.desktop_app.api_client import ApiError, JarvisApiClient
from jarvis.desktop_app.config import AppConfig
from jarvis.desktop_app.strings import tr
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)

_LANGS = [("en", "English"), ("ru", "Русский"), ("uz", "O'zbek")]

# One window: the deck fills it, and everything — chat, voice, models, memory,
# MCP, every setting — lives in there in one design language. The native panels
# below are the fallback for a build without QtWebEngine: no web view means no
# interface, so the app falls back to plain widgets. The owner then gets the
# technical panels too; a signed-in guest still doesn't.
_FALLBACK_USER_TABS = ("chat", "voice")
_FALLBACK_ADMIN_TABS = ("assistant", "capabilities", "integrations", "memory",
                        "general", "logs")


def visible_tabs(role: str, *, webview: bool = True) -> tuple[str, ...]:
    """Ordered tab ids to show.

    With a web view (every shipped build) the answer is always the deck alone.
    Without one, fall back to the native panels ``role`` is allowed to see.
    """
    if webview:
        return ("deck",)
    order = ("chat", "voice", "assistant", "capabilities", "integrations",
            "memory", "general", "logs")
    allowed = set(_FALLBACK_USER_TABS)
    if role != "user":
        allowed |= set(_FALLBACK_ADMIN_TABS)
    return tuple(t for t in order if t in allowed)


def webengine_available() -> bool:
    """True when this build can render the interface."""
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except Exception:  # noqa: BLE001 - lean builds ship without WebEngine
        return False
    return True


_DECK_PAGE_CLASS = None


def deck_page(parent):
    """The page the interface runs on.

    Three things the default page would get wrong for an app: the microphone
    stays blocked (the deck's mic button is real, so it must be allowed), page
    errors vanish (they belong in the app log), and a link to the outside world
    would replace the interface with a web page instead of opening a browser.
    """
    global _DECK_PAGE_CLASS
    if _DECK_PAGE_CLASS is None:
        from PySide6.QtWebEngineCore import QWebEnginePage

        class DeckPage(QWebEnginePage):
            def __init__(self, view) -> None:
                super().__init__(view)
                requested = getattr(self, "permissionRequested", None)
                if requested is not None:      # Qt 6.8+
                    requested.connect(self._on_permission)
                else:  # pragma: no cover - older Qt
                    self.featurePermissionRequested.connect(self._on_feature)

            @staticmethod
            def _on_permission(permission) -> None:
                """Allow the microphone; refuse everything else."""
                from PySide6.QtWebEngineCore import QWebEnginePermission
                wanted = QWebEnginePermission.PermissionType.MediaAudioCapture
                if permission.permissionType() == wanted:
                    permission.grant()
                else:
                    permission.deny()

            def _on_feature(self, origin, feature) -> None:  # pragma: no cover
                from PySide6.QtWebEngineCore import QWebEnginePage as Page
                audio = Page.Feature.MediaAudioCapture
                policy = (Page.PermissionPolicy.PermissionGrantedByUser
                          if feature == audio
                          else Page.PermissionPolicy.PermissionDeniedByUser)
                self.setFeaturePermission(origin, feature, policy)

            def javaScriptConsoleMessage(self, level, message,  # noqa: N802
                                         line, source) -> None:
                logger.debug("interface: %s (%s:%s)", message, source, line)

            def acceptNavigationRequest(self, url, nav_type,  # noqa: N802
                                        is_main_frame) -> bool:
                if is_main_frame and url.scheme() in ("http", "https"):
                    import webbrowser
                    webbrowser.open(url.toString())
                    return False
                return True

        _DECK_PAGE_CLASS = DeckPage
    return _DECK_PAGE_CLASS(parent)

# Chat memory caps — keep RAM bounded on long sessions.
_MAX_RENDER = 150   # messages painted into the transcript widget
_MAX_STORE = 400    # messages kept in memory


def run_app() -> int:
    """Create the Qt application and run the main loop."""
    try:
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QRadioButton,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "The desktop app needs PySide6. Install with: pip install PySide6"
        ) from exc

    config = AppConfig.load()

    class ReplyBridge(QObject):
        """Marshals engine-thread callbacks onto the GUI thread."""

        done = Signal(str, str)  # reply, error
        chunk = Signal(str)      # one streamed piece of the reply
        voice = Signal(str, str, str, str)  # transcript, reply, audio_path, error
        update_ready = Signal(bool, str, str, bool)  # available, latest, url, explicit

    # -- login dialog ---------------------------------------------------------

    class LoginDialog(QDialog):
        def __init__(self) -> None:
            super().__init__()
            self.client: JarvisApiClient | None = None
            loc = config.language
            self.setWindowTitle(tr("login_title", loc))
            self.setMinimumWidth(460)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(28, 28, 28, 28)

            card = QWidget()
            card.setObjectName("Card")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(28, 26, 28, 26)
            layout.setSpacing(12)
            outer.addWidget(card)

            wordmark = QLabel("KER")
            wordmark.setObjectName("Wordmark")
            title = QLabel(tr("login_title", loc))
            title.setObjectName("Title")
            layout.addWidget(wordmark)
            layout.addWidget(title)
            layout.addSpacing(6)

            self.local_radio = QRadioButton(tr("mode_local", loc))
            self.remote_radio = QRadioButton(tr("mode_remote", loc))
            (self.remote_radio if config.mode == "remote"
             else self.local_radio).setChecked(True)
            layout.addWidget(self.local_radio)
            local_hint = QLabel(tr("login_local_hint", loc))
            local_hint.setObjectName("Hint")
            local_hint.setWordWrap(True)
            layout.addWidget(local_hint)
            layout.addWidget(self.remote_radio)
            remote_hint = QLabel(tr("login_remote_hint", loc))
            remote_hint.setObjectName("Hint")
            remote_hint.setWordWrap(True)
            layout.addWidget(remote_hint)

            form = QFormLayout()
            form.setSpacing(10)
            self.server = QLineEdit(config.server_url or "http://localhost:8000")
            self.user = QLineEdit(config.username)
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            for field in (self.server, self.user, self.password):
                field.setMinimumHeight(40)
            form.addRow(tr("server_url", loc), self.server)
            form.addRow(tr("username", loc), self.user)
            form.addRow(tr("password", loc), self.password)
            layout.addSpacing(6)
            layout.addLayout(form)
            layout.addSpacing(8)

            buttons = QHBoxLayout()
            buttons.setSpacing(10)
            sign_in = QPushButton(tr("sign_in", loc))
            sign_in.setObjectName("Primary")
            sign_in.setMinimumHeight(44)
            local = QPushButton(tr("continue_local", loc))
            local.setMinimumHeight(44)
            sign_in.clicked.connect(self._sign_in)
            local.clicked.connect(self._local)
            buttons.addWidget(sign_in, stretch=1)
            buttons.addWidget(local, stretch=1)
            layout.addLayout(buttons)

            tg = QPushButton(tr("sign_in_telegram", loc))
            tg.setMinimumHeight(40)
            tg.clicked.connect(self._telegram_login)
            layout.addWidget(tg)

        def _local(self) -> None:
            config.mode = "local"
            config.role = "admin"      # owner on their own machine
            config.mode_chosen = True
            config.save()
            self.accept()

        def _telegram_login(self) -> None:
            from PySide6.QtWidgets import QInputDialog
            loc = config.language
            code, ok = QInputDialog.getText(
                self, tr("sign_in_telegram", loc), tr("tg_code_prompt", loc))
            if not ok or not code.strip():
                return
            client = JarvisApiClient(self.server.text().strip())
            try:
                client.login_with_telegram_code(code.strip())
            except ApiError as exc:
                QMessageBox.warning(self, tr("login_title", loc),
                                    tr("login_failed", loc, error=exc.detail))
                return
            config.mode = "remote"
            config.role = "user"
            config.server_url = client.base_url
            config.auth_token = client.token
            config.save()
            self.client = client
            self.accept()

        def _sign_in(self) -> None:
            loc = config.language
            client = JarvisApiClient(self.server.text().strip())
            try:
                client.login(self.user.text().strip(), self.password.text())
            except ApiError as exc:
                QMessageBox.warning(self, tr("login_title", loc),
                                    tr("login_failed", loc, error=exc.detail))
                return
            config.mode = "remote"
            config.role = "user"       # signed-in guest — limited app
            config.server_url = client.base_url
            config.username = self.user.text().strip()
            config.auth_token = client.token
            config.save()
            self.client = client
            self.accept()

    # -- main window ------------------------------------------------------

    class MainWindow(QMainWindow):
        def __init__(self, client: JarvisApiClient | None) -> None:
            super().__init__()
            self.client = client
            self.engine_thread = None
            self.bridge = ReplyBridge()
            self.bridge.done.connect(self._on_reply)
            self.bridge.chunk.connect(self._on_chunk)
            self.bridge.update_ready.connect(self._on_update)
            self._streaming = False
            loc = config.language

            self.setWindowTitle(tr("app_title", loc))
            self.resize(1040, 720)
            self.setMinimumSize(880, 600)

            self._webview = webengine_available()
            tabs = QTabWidget()
            builders = {
                "deck": lambda: (self._deck_tab(), "🛰  Command Deck"),
                "chat": lambda: (self._chat_tab(), tr("tab_chat", loc)),
                "voice": lambda: (self._wrap(self._voice_tab(),
                                tr("tab_voice", loc)), tr("tab_voice", loc)),
                "assistant": lambda: (self._wrap(self._assistant_tab(),
                                    tr("tab_assistant", loc)), tr("tab_assistant", loc)),
                "capabilities": lambda: (self._wrap(self._capabilities_tab(),
                                        tr("tab_capabilities", loc)),
                                        tr("tab_capabilities", loc)),
                "integrations": lambda: (self._wrap(self._integrations_tab(),
                                        tr("tab_integrations", loc)),
                                        tr("tab_integrations", loc)),
                "memory": lambda: (self._wrap(self._memory_tab(),
                                tr("tab_memory", loc)), tr("tab_memory", loc)),
                "general": lambda: (self._wrap(self._general_tab(),
                                tr("tab_general", loc)), tr("tab_general", loc)),
                "logs": lambda: (self._logs_tab(), tr("tab_logs", loc)),
            }
            for key in visible_tabs(config.role, webview=self._webview):
                widget, title = builders[key]()
                tabs.addTab(widget, title)
            # One tab = one window: hide the tab bar so the deck reads as the app.
            if tabs.count() == 1:
                tabs.tabBar().hide()

            container = QWidget()
            root = QVBoxLayout(container)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            if self._webview:
                # The interface brings its own title bar, rail and status bar —
                # a native header on top of it would just say KER twice.
                root.addWidget(tabs, stretch=1)
            else:
                root.addWidget(self._header())
                body = QWidget()
                body_layout = QVBoxLayout(body)
                body_layout.setContentsMargins(18, 8, 18, 18)
                body_layout.addWidget(tabs)
                root.addWidget(body, stretch=1)
            self.setCentralWidget(container)

            self.voice_controller = None
            self._force_quit = False
            self.tray = None
            self._build_tray()
            if config.mode == "local":
                self._start_local_engine()
                self._init_voice()
            # Auto-update opt-in: quietly check on launch.
            if getattr(config, "auto_update", False):
                self._check_updates(explicit=False)

        # -- system tray ------------------------------------------------------

        def _tray_icon(self):
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
            from jarvis.desktop_app.theme import THEMES
            accent = THEMES.get(config.theme, THEMES["obsidian"])["accent"]
            pix = QPixmap(64, 64)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor(accent)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(8, 8, 48, 48)
            painter.setBrush(QBrush(QColor("#0b0f14")))
            painter.drawEllipse(24, 24, 16, 16)
            painter.end()
            return QIcon(pix)

        def _build_tray(self) -> None:
            from PySide6.QtWidgets import QMenu, QSystemTrayIcon
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            loc = config.language
            self.tray = QSystemTrayIcon(self._tray_icon(), self)
            self.tray.setToolTip("KER")
            menu = QMenu()
            show = menu.addAction(tr("tray_show", loc))
            show.triggered.connect(self._restore)
            upd = menu.addAction("🔄 " + tr("check_updates", loc))
            upd.triggered.connect(lambda: self._check_updates(explicit=True))
            quit_action = menu.addAction(tr("tray_quit", loc))
            quit_action.triggered.connect(self._quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()
            self.setWindowIcon(self._tray_icon())

        def _tray_activated(self, reason) -> None:
            from PySide6.QtWidgets import QSystemTrayIcon
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self._restore()

        # -- updates ----------------------------------------------------------

        def _check_updates(self, *, explicit: bool = False) -> None:
            """Check GitHub for a newer release; offer to open the download."""
            import threading

            from jarvis import __version__
            from jarvis.core.updater import check_github

            def _work() -> None:
                info = check_github(
                    __version__,
                    include_prerelease=(config.update_channel != "stable"))
                self.bridge.update_ready.emit(info.available, info.latest,
                                            info.download_url or info.url,
                                            explicit)

            threading.Thread(target=_work, daemon=True).start()

        def _on_update(self, available: bool, latest: str, url: str,
                    explicit: bool) -> None:
            from PySide6.QtWidgets import QMessageBox
            if not available:
                if explicit:
                    QMessageBox.information(self, "KER",
                                            "У вас последняя версия.")
                return
            # Auto-update (opt-in): apply straight away; otherwise ask.
            if config.auto_update and url:
                self._apply_update(url, latest)
                return
            ans = QMessageBox.question(
                self, "Доступно обновление",
                f"Вышла версия {latest}. Установить сейчас?")
            if ans == QMessageBox.StandardButton.Yes and url:
                self._apply_update(url, latest)

        def _apply_update(self, url: str, latest: str = "") -> None:
            """Download the Windows installer and launch it silently, then quit.

            On non-Windows or for a non-installer URL, just open the download.
            """
            import sys
            import tempfile
            import webbrowser
            from pathlib import Path

            from jarvis.core.updater import download
            if sys.platform != "win32" or not url.lower().endswith(".exe"):
                webbrowser.open(url)
                return
            dest = Path(tempfile.gettempdir()) / "KER-Setup.exe"
            try:
                download(url, str(dest))
            except Exception:  # noqa: BLE001 - fall back to the browser
                webbrowser.open(url)
                return
            import subprocess
            try:
                # Inno Setup silent install; it replaces files after we exit.
                subprocess.Popen([str(dest), "/VERYSILENT", "/NORESTART"],
                                close_fds=True)
            except Exception:  # noqa: BLE001 - run the installer normally
                import os
                os.startfile(str(dest))  # type: ignore[attr-defined]  # noqa: S606
            self._quit()

        def _restore(self) -> None:
            self.showNormal()
            self.raise_()
            self.activateWindow()

        def _quit(self) -> None:
            self._force_quit = True
            self.close()

        def _header(self) -> "QWidget":
            bar = QWidget()
            bar.setObjectName("Header")
            bar.setFixedHeight(64)
            row = QHBoxLayout(bar)
            row.setContentsMargins(20, 0, 20, 0)

            wordmark = QLabel("KER")
            wordmark.setObjectName("Wordmark")
            row.addWidget(wordmark)

            mode_text = ("● local" if config.mode == "local"
                        else f"● {config.username or 'account'}")
            mode = QLabel(mode_text)
            mode.setObjectName("Subtle")
            row.addSpacing(14)
            row.addWidget(mode)

            row.addStretch(1)
            status = QLabel("● online")
            status.setObjectName("StatusDot")
            row.addWidget(status)
            return bar

        # -- engine -----------------------------------------------------------

        def _start_local_engine(self) -> None:
            from jarvis.config.settings import Settings
            from jarvis.desktop_app.engine_thread import EngineThread

            overrides = config.to_settings_overrides()
            settings = Settings(**overrides)
            self.engine_thread = EngineThread(settings)
            try:
                self.engine_thread.start()
            except Exception as exc:  # noqa: BLE001 - shown in the chat view
                self._append_system(tr("error", config.language, error=exc))
                return
            # Serve a local API over the running engine so the Command Deck is
            # live in-window (real data), not just demo. Best-effort.
            try:
                self._local_api = self.engine_thread.start_api()
            except Exception:  # noqa: BLE001 - deck falls back to demo mode
                self._local_api = None

        #: Saving one of these changes what the engine *is*, so it is rebuilt.
        ENGINE_FIELDS = frozenset({
            "assistant_name", "language", "llm_provider", "llm_model",
            "anthropic_api_key", "openai_api_key", "allow_file_read",
            "allow_file_write", "allow_shell", "allow_desktop_control",
            "workspace_root", "voice_enabled", "voice_replies", "stt_backend",
            "tts_backend", "tts_voice", "weather_enabled", "homeassistant_url",
            "homeassistant_token", "telegram_bot_token",
            "telegram_send_enabled", "telegram_channel",
        })

        def on_settings_changed(self, changed: set[str]) -> None:
            """React to a save the interface just made (on the GUI thread).

            A setting the user flips has to mean something immediately, so the
            look is restyled here and the engine is rebuilt when the change is
            one it was constructed from.
            """
            changed = set(changed or ())
            if "theme" in changed:
                self._restyle(config.theme)
            if "start_on_boot" in changed:
                try:
                    import sys as _sys

                    from jarvis.desktop_app import autostart
                    autostart.set_enabled(config.start_on_boot,
                                        f'"{_sys.executable}"')
                except Exception as exc:  # noqa: BLE001 - config still saved
                    logger.warning("Autostart update failed: %s", exc)
            if config.mode == "local" and (changed & self.ENGINE_FIELDS):
                self._restart_engine()

        def _restart_engine(self) -> None:
            """Rebuild the engine so new settings are actually in force."""
            old = self.engine_thread
            self.engine_thread = None
            self.voice_controller = None
            self._local_api = None
            if old is not None:
                try:
                    old.stop()
                except Exception as exc:  # noqa: BLE001 - restart anyway
                    logger.warning("Engine stop failed: %s", exc)
            self._start_local_engine()
            self._init_voice()
            self._push_connection()

        def _restyle(self, theme: str) -> None:
            """Repaint both layers — the native shell and the interface."""
            from jarvis.desktop_app.theme import stylesheet
            QApplication.instance().setStyleSheet(stylesheet(theme))
            view = getattr(self, "_deck_view", None)
            if view is not None:
                view.page().runJavaScript(
                    f"applyTheme({theme!r},{{persist:false}});")
            if self.tray is not None:
                self.tray.setIcon(self._tray_icon())
                self.setWindowIcon(self._tray_icon())

        def _init_voice(self) -> None:
            if self.engine_thread is None or not config.voice_enabled:
                return
            try:
                from jarvis.config.settings import Settings
                from jarvis.desktop_app.voice_controller import VoiceController
                from jarvis.voice import VoiceService

                settings = Settings(**config.to_settings_overrides())
                voice = VoiceService.from_settings(settings)
                self.voice_controller = VoiceController(
                    voice, self.engine_thread
                )
                self._update_voice_ui()
            except Exception as exc:  # noqa: BLE001 - voice is optional
                logger.warning("Voice init failed: %s", exc)

        def _wrap(self, inner: "QWidget", title: str,
                subtitle: str = "") -> "QWidget":
            """Put a settings widget in a centred, scrollable card with a header."""
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (
                QLabel,
                QScrollArea,
                QVBoxLayout,
                QWidget,
            )
            page = QWidget()
            outer = QVBoxLayout(page)
            outer.setContentsMargins(0, 0, 0, 0)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            host = QWidget()
            hl = QVBoxLayout(host)
            hl.setContentsMargins(36, 26, 36, 26)
            hl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            card = QWidget()
            card.setObjectName("Card")
            card.setMaximumWidth(760)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(30, 26, 30, 28)
            cl.setSpacing(16)
            header = QLabel(title)
            header.setObjectName("PageTitle")
            cl.addWidget(header)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setObjectName("PageSub")
                sub.setWordWrap(True)
                cl.addWidget(sub)
            cl.addWidget(inner)
            hl.addWidget(card)
            scroll.setWidget(host)
            outer.addWidget(scroll)
            return page

        # -- command deck (web dashboard) --------------------------------

        @staticmethod
        def _deck_html() -> str:
            """Read the desktop interface, working in dev and frozen builds.

            The desktop app has its **own** UI (``static/desktop.html``) — the
            browser dashboard is a separate product and evolves independently,
            so the two must never share a file.
            """
            from jarvis.desktop_app.assets import interface_html
            return interface_html("desktop.html")

        def _deck_conn(self) -> tuple[str, str]:
            """API endpoint + key to hand the dashboard.

            Local mode serves a live API over the running engine; remote mode
            points at the configured server. Empty = demo mode.
            """
            local = getattr(self, "_local_api", None)
            if config.mode == "local" and local:
                return local
            if config.mode == "remote" and config.server_url:
                return config.server_url, config.auth_token or ""
            return "", ""

        def _deck_tab(self) -> "QWidget":
            from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            try:
                from PySide6.QtCore import QUrl
                from PySide6.QtWebEngineWidgets import QWebEngineView
            except Exception:  # noqa: BLE001 - WebEngine excluded from lean builds
                lbl = QLabel("Command Deck opens in your browser.\n"
                            "(A full in-window build needs PySide6 QtWebEngine.)")
                lbl.setWordWrap(True)
                btn = QPushButton("🛰  Open Command Deck")
                btn.clicked.connect(self._open_deck_browser)
                lay.setContentsMargins(36, 30, 36, 30)
                lay.addWidget(lbl)
                lay.addWidget(btn)
                lay.addStretch(1)
                return page
            view = QWebEngineView()
            # Served from the app's own scheme, so the page shares an origin
            # with the bridge it calls and keeps its preferences between runs.
            from jarvis.desktop_app.webbridge import BASE_URL
            view.setPage(deck_page(view))
            view.load(QUrl(BASE_URL))

            def _inject(ok: bool) -> None:
                """Hand the deck its connection and the app's theme."""
                if not ok:
                    return
                api, key = self._deck_conn()
                js = f"applyTheme({config.theme!r},{{persist:false}});"
                if api or key:
                    js += f"CFG.api={api!r};CFG.key={key!r};loadState();refreshVoice();"
                view.page().runJavaScript(js)
                self._deck_ready = True
                self._flush_greeting()
            self._deck_view = view
            self._deck_ready = False

            view.loadFinished.connect(_inject)
            lay.addWidget(view)
            return page

        def _push_connection(self) -> None:
            """Point the deck at the (re)started local API."""
            view = getattr(self, "_deck_view", None)
            if view is None:
                return
            api, key = self._deck_conn()
            view.page().runJavaScript(
                f"CFG.api={api!r};CFG.key={key!r};loadState();refreshVoice();")

        def _open_deck_browser(self) -> None:
            import tempfile
            import webbrowser
            from pathlib import Path
            tmp = Path(tempfile.gettempdir()) / "jarvis_command_deck.html"
            tmp.write_text(self._deck_html(), encoding="utf-8")
            webbrowser.open(tmp.as_uri())

        # -- chat tab -----------------------------------------------------

        def _chat_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)

            top = QHBoxLayout()
            top.addWidget(QLabel(tr("language", loc)))
            self.lang_box = QComboBox()
            for code, label in _LANGS:
                self.lang_box.addItem(label, code)
                if code == loc:
                    self.lang_box.setCurrentIndex(self.lang_box.count() - 1)
            self.lang_box.currentIndexChanged.connect(self._change_language)
            top.addWidget(self.lang_box)

            top.addSpacing(16)
            top.addWidget(QLabel(tr("theme", loc)))
            from jarvis.desktop_app.theme import theme_names
            self.theme_box = QComboBox()
            for key, label in theme_names():
                self.theme_box.addItem(label, key)
                if key == config.theme:
                    self.theme_box.setCurrentIndex(self.theme_box.count() - 1)
            self.theme_box.currentIndexChanged.connect(self._change_theme)
            top.addWidget(self.theme_box)

            top.addStretch(1)
            layout.addLayout(top)

            self.transcript = QTextEdit()
            self.transcript.setReadOnly(True)
            self.transcript.setFrameStyle(0)
            layout.addWidget(self.transcript, stretch=1)
            self._messages: list[tuple[str, str]] = []
            self._pending = False

            row = QHBoxLayout()
            row.setSpacing(10)
            self.input = QLineEdit()
            self.input.setPlaceholderText("Message KER …")
            self.input.setMinimumHeight(44)
            self.input.returnPressed.connect(self._send)
            send = QPushButton(tr("send", loc))
            send.setObjectName("Primary")
            send.setMinimumHeight(44)
            send.clicked.connect(self._send)
            row.addWidget(self.input, stretch=1)
            row.addWidget(send)
            layout.addLayout(row)
            return widget

        def _render_chat(self) -> None:
            from jarvis.desktop_app.theme import bubble_html
            th = config.theme
            # Render only the most recent messages so a long session doesn't
            # grow the widget (and RAM) without bound.
            visible = self._messages[-_MAX_RENDER:]
            html = "".join(bubble_html(r, t, th) for r, t in visible)
            if self._pending:
                html += bubble_html("system", tr("thinking", config.language), th)
            self.transcript.setHtml(html)
            bar = self.transcript.verticalScrollBar()
            bar.setValue(bar.maximum())

        def _append_system(self, text: str) -> None:
            if not hasattr(self, "transcript"):
                # The interface is a web view — it has no native transcript to
                # write into, so the note goes to the log the app can show.
                logger.warning("%s", text)
                return
            self._messages.append(("system", text))
            self._render_chat()

        def _change_language(self) -> None:
            config.language = self.lang_box.currentData()
            config.save()
            if self.engine_thread is not None:
                session = self.engine_thread.engine.session("desktop")
                session.scratch["language"] = config.language

        def _change_theme(self) -> None:
            """Apply the chosen theme to both layers of the app."""
            config.theme = self.theme_box.currentData()
            config.save()
            self._restyle(config.theme)

        def _send(self) -> None:
            text = self.input.text().strip()
            if not text:
                return
            loc = config.language
            self.input.clear()
            self._messages.append(("user", text))
            # Cap stored history so memory stays bounded on long sessions.
            if len(self._messages) > _MAX_STORE:
                self._messages = self._messages[-_MAX_STORE:]
            self._pending = True
            self._render_chat()

            self._streaming = False
            if config.mode == "remote" and self.client is not None:
                import threading

                def _worker() -> None:
                    try:
                        self.client.chat_stream(
                            text, on_chunk=self.bridge.chunk.emit
                        )
                        self.bridge.done.emit("", "")
                    except ApiError as exc:
                        self.bridge.done.emit("", exc.detail)

                threading.Thread(target=_worker, daemon=True).start()
            elif self.engine_thread is not None:
                session = self.engine_thread.engine.session("desktop")
                session.scratch["language"] = config.language
                self.engine_thread.stream_async(
                    text,
                    on_chunk=self.bridge.chunk.emit,
                    on_done=lambda err: self.bridge.done.emit(
                        "", str(err) if err else ""
                    ),
                )
            else:
                self.bridge.done.emit("", tr("not_signed_in", loc))

        def _on_chunk(self, text: str) -> None:
            if not self._streaming:
                self._streaming = True
                self._pending = False
                self._messages.append(("assistant", ""))
            role, prev = self._messages[-1]
            self._messages[-1] = ("assistant", prev + text)
            self._render_chat()

        def _on_reply(self, reply: str, error: str) -> None:
            loc = config.language
            self._pending = False
            was_streaming = self._streaming
            self._streaming = False
            if error:
                self._append_system(tr("error", loc, error=error))
            elif reply and not was_streaming:
                self._messages.append(("assistant", reply))
                self._render_chat()
            # Toast when a reply finishes and the window isn't focused.
            if not error:
                last = self._messages[-1][1] if self._messages else ""
                self._notify(reply or last)

        # -- voice tab -----------------------------------------------------

        def _voice_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)

            self.voice_status = QLabel(tr("voice_unavailable_desktop", loc))
            self.voice_status.setWordWrap(True)
            layout.addWidget(self.voice_status)

            self.voice_button = QPushButton(tr("voice_record", loc))
            self.voice_button.setObjectName("Record")
            self.voice_button.setEnabled(False)
            self.voice_button.setMinimumHeight(64)
            self.voice_button.clicked.connect(self._toggle_recording)
            layout.addWidget(self.voice_button)

            self.voice_speak = QCheckBox(tr("voice_speak_replies", loc))
            self.voice_speak.setChecked(True)
            layout.addWidget(self.voice_speak)

            # -- voice engine settings --
            settings_form = QFormLayout()
            self.stt_box = QComboBox()
            self.stt_box.addItems(["openai", "local"])
            self.stt_box.setCurrentText(config.stt_backend)
            self.tts_box = QComboBox()
            self.tts_box.addItems(["openai", "edge", "gtts"])
            self.tts_box.setCurrentText(config.tts_backend)
            self.tts_voice_edit = QLineEdit(config.tts_voice)
            self.whisper_box = QComboBox()
            self.whisper_box.addItems(["tiny", "base", "small", "medium", "large"])
            self.whisper_box.setCurrentText(config.local_whisper_model)
            settings_form.addRow(tr("stt_backend", loc), self.stt_box)
            settings_form.addRow(tr("tts_backend", loc), self.tts_box)
            settings_form.addRow(tr("tts_voice", loc), self.tts_voice_edit)
            settings_form.addRow(tr("whisper_model", loc), self.whisper_box)
            layout.addLayout(settings_form)

            self.voice_enable = QCheckBox(tr("voice_replies_opt", loc))
            self.voice_enable.setChecked(config.voice_replies)
            layout.addWidget(self.voice_enable)

            save_voice = QPushButton(tr("save", loc))
            save_voice.setObjectName("Primary")
            save_voice.setMinimumHeight(40)
            save_voice.clicked.connect(self._save_voice)
            layout.addWidget(save_voice)

            self.voice_output = QTextEdit()
            self.voice_output.setReadOnly(True)
            layout.addWidget(self.voice_output, stretch=1)

            self._recording = False
            self._recorder = None
            self._capture = None
            self._audio_in = None
            self._player = None
            self._audio_out = None
            self._voice_file = ""
            self.bridge.voice.connect(self._on_voice_result)
            return widget

        def _save_voice(self) -> None:
            config.stt_backend = self.stt_box.currentText()
            config.tts_backend = self.tts_box.currentText()
            config.tts_voice = self.tts_voice_edit.text().strip() or "alloy"
            config.local_whisper_model = self.whisper_box.currentText()
            config.voice_replies = self.voice_enable.isChecked()
            config.voice_enabled = True
            config.save()
            QMessageBox.information(self, "KER",
                                    tr("saved", config.language))

        def _update_voice_ui(self) -> None:
            loc = config.language
            if self.voice_controller is not None and self.voice_controller.available():
                self.voice_status.setText("")
                self.voice_button.setEnabled(True)
            else:
                self.voice_status.setText(tr("voice_unavailable_desktop", loc))
                self.voice_button.setEnabled(False)

        def _toggle_recording(self) -> None:
            loc = config.language
            if self._recording:
                self._recording = False
                self.voice_button.setText(tr("voice_record", loc))
                if self._recorder is not None:
                    self._recorder.stop()
                return

            try:
                import tempfile

                from PySide6.QtCore import QUrl
                from PySide6.QtMultimedia import (
                    QAudioInput,
                    QMediaCaptureSession,
                    QMediaFormat,
                    QMediaRecorder,
                )
            except ImportError as exc:
                self.voice_status.setText(tr("error", loc, error=exc))
                return

            self._voice_file = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ).name
            self._capture = QMediaCaptureSession()
            self._audio_in = QAudioInput()
            self._capture.setAudioInput(self._audio_in)
            self._recorder = QMediaRecorder()
            self._capture.setRecorder(self._recorder)
            fmt = QMediaFormat()
            fmt.setFileFormat(QMediaFormat.FileFormat.Wave)
            self._recorder.setMediaFormat(fmt)
            self._recorder.setOutputLocation(QUrl.fromLocalFile(self._voice_file))
            self._recorder.recorderStateChanged.connect(self._on_recorder_state)
            self._recording = True
            self.voice_button.setText(tr("voice_stop", loc))
            self._recorder.record()

        def _on_recorder_state(self, state) -> None:
            from PySide6.QtMultimedia import QMediaRecorder

            if state != QMediaRecorder.RecorderState.StoppedState:
                return
            loc = config.language
            self.voice_status.setText(tr("voice_processing", loc))

            import threading
            from pathlib import Path

            path = self._voice_file
            speak = self.voice_speak.isChecked()

            def _worker() -> None:
                try:
                    audio = Path(path).read_bytes()
                    controller = self.voice_controller
                    controller.speak_replies = speak
                    turn = controller.run_turn(audio, filename="voice.wav")
                    out_path = ""
                    if turn.reply_audio:
                        import tempfile
                        out = tempfile.NamedTemporaryFile(
                            suffix=f".{turn.reply_audio_ext}", delete=False
                        )
                        out.write(turn.reply_audio)
                        out.close()
                        out_path = out.name
                    self.bridge.voice.emit(turn.transcript, turn.reply,
                                        out_path, "")
                except Exception as exc:  # noqa: BLE001 - shown in the UI
                    self.bridge.voice.emit("", "", "", str(exc))
                finally:
                    Path(path).unlink(missing_ok=True)

            threading.Thread(target=_worker, daemon=True).start()

        def _on_voice_result(self, transcript: str, reply: str,
                            audio_path: str, error: str) -> None:
            loc = config.language
            self.voice_status.setText("")
            if error:
                self.voice_output.append(f"<i>{tr('error', loc, error=error)}</i>")
                return
            if not transcript:
                self.voice_output.append(
                    f"<i>{tr('voice_no_speech', loc)}</i>")
                return
            self.voice_output.append(
                f"<b>{tr('voice_you_said', loc)}:</b> {transcript}")
            self.voice_output.append(f"<b>KER:</b> {reply}")
            # Mirror the exchange into the chat transcript.
            self._messages.append(("user", f"🎙 {transcript}"))
            self._messages.append(("assistant", reply))
            self._render_chat()
            if audio_path:
                self._play_audio(audio_path)

        def _play_audio(self, path: str) -> None:
            try:
                from PySide6.QtCore import QUrl
                from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            except ImportError:
                return
            self._player = QMediaPlayer()
            self._audio_out = QAudioOutput()
            self._player.setAudioOutput(self._audio_out)
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()

        # -- assistant tab ------------------------------------------------

        def _assistant_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            form = QFormLayout(widget)

            self.provider_box = QComboBox()
            self.provider_box.addItems(["anthropic", "openai", "openrouter"])
            self.provider_box.setCurrentText(config.llm_provider)
            self.model_edit = QLineEdit(config.llm_model)
            self.anthropic_edit = QLineEdit(config.anthropic_api_key)
            self.anthropic_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.openai_edit = QLineEdit(config.openai_api_key)
            self.openai_edit.setEchoMode(QLineEdit.EchoMode.Password)

            form.addRow(tr("provider", loc), self.provider_box)
            form.addRow(tr("model", loc), self.model_edit)
            form.addRow(tr("anthropic_key", loc), self.anthropic_edit)
            form.addRow(tr("openai_key", loc), self.openai_edit)

            save = QPushButton(tr("save", loc))
            save.setObjectName("Primary")
            save.setMinimumHeight(40)
            save.clicked.connect(self._save_assistant)
            form.addRow(save)
            return widget

        def _save_assistant(self) -> None:
            config.llm_provider = self.provider_box.currentText()
            config.llm_model = self.model_edit.text().strip()
            config.anthropic_api_key = self.anthropic_edit.text().strip()
            config.openai_api_key = self.openai_edit.text().strip()
            config.save()
            QMessageBox.information(self, "KER",
                                    tr("saved", config.language))

        # -- capabilities tab (granular PC access) --------------------------

        def _capabilities_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)
            intro = QLabel(tr("cap_intro", loc))
            intro.setWordWrap(True)
            layout.addWidget(intro)

            self.cap_read = QCheckBox(tr("cap_file_read", loc))
            self.cap_read.setChecked(config.allow_file_read)
            self.cap_write = QCheckBox(tr("cap_file_write", loc))
            self.cap_write.setChecked(config.allow_file_write)
            self.cap_shell = QCheckBox(tr("cap_shell", loc))
            self.cap_shell.setChecked(config.allow_shell)
            self.cap_desktop = QCheckBox(tr("cap_desktop", loc))
            self.cap_desktop.setChecked(config.allow_desktop_control)
            for box in (self.cap_read, self.cap_write, self.cap_shell,
                        self.cap_desktop):
                layout.addWidget(box)

            form = QFormLayout()
            self.workspace_edit = QLineEdit(config.workspace_root)
            form.addRow(tr("workspace", loc), self.workspace_edit)
            layout.addLayout(form)

            save = QPushButton(tr("save", loc))
            save.setObjectName("Primary")
            save.setMinimumHeight(40)
            save.clicked.connect(self._save_capabilities)
            layout.addWidget(save)
            layout.addStretch(1)
            return widget

        def _save_capabilities(self) -> None:
            config.allow_file_read = self.cap_read.isChecked()
            config.allow_file_write = self.cap_write.isChecked()
            config.allow_shell = self.cap_shell.isChecked()
            config.allow_desktop_control = self.cap_desktop.isChecked()
            config.workspace_root = self.workspace_edit.text().strip()
            config.save()
            QMessageBox.information(self, "KER",
                                    tr("saved", config.language))

        # -- integrations tab ---------------------------------------------

        def _integrations_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)

            self.int_weather = QCheckBox(tr("int_weather", loc))
            self.int_weather.setChecked(config.weather_enabled)
            layout.addWidget(self.int_weather)

            form = QFormLayout()
            self.ha_url = QLineEdit(config.homeassistant_url)
            self.ha_token = QLineEdit(config.homeassistant_token)
            self.ha_token.setEchoMode(QLineEdit.EchoMode.Password)
            self.tg_token = QLineEdit(config.telegram_bot_token)
            self.tg_token.setEchoMode(QLineEdit.EchoMode.Password)
            self.tg_channel = QLineEdit(config.telegram_channel)
            form.addRow(tr("int_ha_url", loc), self.ha_url)
            form.addRow(tr("int_ha_token", loc), self.ha_token)
            form.addRow(tr("int_tg_token", loc), self.tg_token)
            form.addRow(tr("int_tg_channel", loc), self.tg_channel)
            layout.addLayout(form)

            self.tg_send = QCheckBox(tr("int_tg_send", loc))
            self.tg_send.setChecked(config.telegram_send_enabled)
            layout.addWidget(self.tg_send)

            save = QPushButton(tr("save", loc))
            save.setObjectName("Primary")
            save.setMinimumHeight(40)
            save.clicked.connect(self._save_integrations)
            layout.addWidget(save)
            layout.addStretch(1)
            return widget

        def _save_integrations(self) -> None:
            config.weather_enabled = self.int_weather.isChecked()
            config.homeassistant_url = self.ha_url.text().strip()
            config.homeassistant_token = self.ha_token.text().strip()
            config.telegram_bot_token = self.tg_token.text().strip()
            config.telegram_channel = self.tg_channel.text().strip()
            config.telegram_send_enabled = self.tg_send.isChecked()
            config.save()
            QMessageBox.information(self, "KER",
                                    tr("saved", config.language))

        # -- memory tab -----------------------------------------------------

        def _memory_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)

            reset = QPushButton(tr("mem_reset", loc))
            forget = QPushButton(tr("mem_forget", loc))
            reset.clicked.connect(lambda: self._memory_action("reset"))
            forget.clicked.connect(lambda: self._memory_action("forget"))
            layout.addWidget(reset)
            layout.addWidget(forget)

            link = QPushButton(tr("link_telegram", loc))
            link.clicked.connect(self._link_telegram)
            layout.addWidget(link)

            self.memory_status = QLabel("")
            layout.addWidget(self.memory_status)
            layout.addStretch(1)
            return widget

        def _memory_action(self, action: str) -> None:
            loc = config.language
            try:
                if self.engine_thread is not None:
                    getattr(self.engine_thread, action)()
                self.memory_status.setText(tr("mem_done", loc))
            except Exception as exc:  # noqa: BLE001 - shown in the UI
                self.memory_status.setText(tr("error", loc, error=exc))

        def _link_telegram(self) -> None:
            loc = config.language
            if self.client is None:
                self.memory_status.setText(tr("not_signed_in", loc))
                return
            try:
                code = self.client.pairing_code()
            except ApiError as exc:
                self.memory_status.setText(tr("error", loc, error=exc.detail))
                return
            self.memory_status.setText(tr("link_code_info", loc, code=code))

        # -- general tab ------------------------------------------------------

        def _general_tab(self) -> "QWidget":
            loc = config.language
            widget = QWidget()
            layout = QVBoxLayout(widget)

            # Theme picker — restyles the native shell *and* the Command Deck.
            row = QHBoxLayout()
            row.addWidget(QLabel(tr("theme", loc)))
            from jarvis.desktop_app.theme import theme_names
            self.theme_box = QComboBox()
            for key, label in theme_names():
                self.theme_box.addItem(label, key)
                if key == config.theme:
                    self.theme_box.setCurrentIndex(self.theme_box.count() - 1)
            self.theme_box.currentIndexChanged.connect(self._change_theme)
            row.addWidget(self.theme_box, stretch=1)
            layout.addLayout(row)

            self.opt_tray = QCheckBox(tr("opt_tray", loc))
            self.opt_tray.setChecked(config.minimize_to_tray)
            self.opt_boot = QCheckBox(tr("opt_boot", loc))
            self.opt_boot.setChecked(config.start_on_boot)
            self.opt_notify = QCheckBox(tr("opt_notify", loc))
            self.opt_notify.setChecked(config.notifications)
            for box in (self.opt_tray, self.opt_boot, self.opt_notify):
                layout.addWidget(box)

            save = QPushButton(tr("save", loc))
            save.setObjectName("Primary")
            save.setMinimumHeight(40)
            save.clicked.connect(self._save_general)
            layout.addWidget(save)
            layout.addStretch(1)
            return widget

        def _save_general(self) -> None:
            config.minimize_to_tray = self.opt_tray.isChecked()
            config.start_on_boot = self.opt_boot.isChecked()
            config.notifications = self.opt_notify.isChecked()
            config.save()
            try:
                import sys

                from jarvis.desktop_app import autostart
                autostart.set_enabled(config.start_on_boot,
                                    f'"{sys.executable}"')
            except Exception as exc:  # noqa: BLE001 - shown to the user
                logger.warning("Autostart update failed: %s", exc)
            QMessageBox.information(self, "KER",
                                    tr("saved", config.language))

        # -- logs tab ---------------------------------------------------------

        def _logs_tab(self) -> "QWidget":
            widget = QWidget()
            layout = QVBoxLayout(widget)
            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            layout.addWidget(self.log_view)

            refresh = QPushButton("⟳")
            refresh.clicked.connect(self._refresh_logs)
            layout.addWidget(refresh)
            self._refresh_logs()
            return widget

        def _refresh_logs(self) -> None:
            from pathlib import Path
            for candidate in ("logs/jarvis.log", "logs/audit.log"):
                path = Path(candidate)
                if path.exists():
                    lines = path.read_text(encoding="utf-8",
                                        errors="replace").splitlines()[-500:]
                    self.log_view.setPlainText("\n".join(lines))
                    return
            self.log_view.setPlainText("(no logs yet)")

        # -- onboarding + notifications ---------------------------------------

        def maybe_onboard(self) -> None:
            """Greet a first-time user — inside the interface, not on top of it."""
            if config.onboarded:
                return
            loc = config.language
            if getattr(self, "_deck_view", None) is not None:
                # Held until the deck has loaded — it cannot be told anything
                # before its own script has run.
                self._greeting = (f"{tr('welcome_title', loc)} — "
                                f"{tr('welcome_body', loc)}")
                self._flush_greeting()
            else:
                QMessageBox.information(self, tr("welcome_title", loc),
                                        tr("welcome_body", loc))
            config.onboarded = True
            config.save()

        def _flush_greeting(self) -> None:
            """Show the held greeting if the deck is ready for it."""
            text = getattr(self, "_greeting", "")
            view = getattr(self, "_deck_view", None)
            if not text or view is None or not getattr(self, "_deck_ready", False):
                return
            self._greeting = ""
            import json
            view.page().runJavaScript(f"toast({json.dumps(text)})")

        def _notify(self, text: str) -> None:
            if (self.tray is not None and config.notifications
                    and not self.isActiveWindow()):
                from PySide6.QtWidgets import QSystemTrayIcon
                self.tray.showMessage(
                    tr("notify_reply", config.language), text[:140],
                    QSystemTrayIcon.MessageIcon.Information, 4000)

        # -- shutdown -------------------------------------------------------

        def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
            if (not self._force_quit and self.tray is not None
                    and config.minimize_to_tray):
                event.ignore()
                self.hide()
                self.tray.showMessage(
                    "KER", tr("tray_running", config.language))
                return
            if self.engine_thread is not None:
                self.engine_thread.stop()
            if self.tray is not None:
                self.tray.hide()
            event.accept()

    # -- the way in, in the same design -----------------------------------

    class WebLoginWindow(QDialog):
        """The sign-in screen — the interface's own, not a native dialog.

        Shows ``desktop_login.html`` and closes itself the moment the bridge
        reports a successful sign-in, whichever of the three ways was used.
        """

        def __init__(self, handler) -> None:
            super().__init__()
            from PySide6.QtCore import QUrl
            from PySide6.QtWebEngineWidgets import QWebEngineView

            from jarvis.desktop_app.webbridge import BASE_URL
            self.setWindowTitle(tr("login_title", config.language))
            self.resize(960, 620)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            view = QWebEngineView()
            view.setPage(deck_page(view))
            view.load(QUrl(BASE_URL + "login"))
            layout.addWidget(view)
            handler.signals.signed_in.connect(self.accept)

    from PySide6.QtGui import QFont

    from jarvis.desktop_app.assets import DECK, interface_html, login_page
    from jarvis.desktop_app.bridge import Bridge
    from jarvis.desktop_app.theme import stylesheet

    webview = webengine_available()
    bridge = Bridge(config)
    if webview:
        # The scheme has to exist before the engine starts up.
        from jarvis.desktop_app import webbridge
        webbridge.register_scheme()

    app = QApplication([])
    app.setApplicationName("KER")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(stylesheet(config.theme))

    #: Filled in once the window exists, so saves made from the interface
    #: reach the app that has to act on them.
    window_ref: dict = {}

    def _on_change(changed) -> None:
        window = window_ref.get("window")
        if window is not None:
            window.on_settings_changed(set(changed or ()))

    handler = None
    if webview:
        from PySide6.QtWebEngineCore import QWebEngineProfile
        handler = webbridge.install(
            QWebEngineProfile.defaultProfile(),
            bridge=bridge,
            pages={"/": lambda: interface_html(DECK),
                   "/login": lambda: login_page(config)},
            on_change=_on_change,
        )

    client: JarvisApiClient | None = None
    if config.mode == "remote" and config.auth_token and config.server_url:
        # Try the saved token first; fall back to the sign-in screen.
        candidate = JarvisApiClient(config.server_url, token=config.auth_token)
        try:
            candidate.me()
            client = candidate
        except ApiError:
            config.auth_token = ""
            config.save()

    # A local owner has already answered this question — don't ask every launch.
    if client is None and not (config.mode == "local" and config.mode_chosen):
        if handler is not None:
            login = WebLoginWindow(handler)
            if login.exec() != QDialog.DialogCode.Accepted:
                return 0
            client = bridge.client
        else:  # no web view in this build: the plain dialog still works
            dialog = LoginDialog()
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
            client = dialog.client

    window = MainWindow(client)
    window_ref["window"] = window
    window.show()
    window.maybe_onboard()
    return app.exec()
