"""
The app's own URL scheme — how the interface and the app talk.

The interface is *served* at ``ker://deck/`` rather than pasted into the view,
and that buys three things:

* one origin — the page, the bridge and the app agree on who they are, so the
  browser engine does not refuse the page's own calls;
* real storage — the page keeps its preferences between runs;
* native actions as ordinary requests — ``fetch("ker://deck/call/settings.save")``
  is answered by :class:`jarvis.desktop_app.bridge.Bridge`.

Actions run on a worker thread, so a slow sign-in cannot freeze the window; the
result is handed back to the request when it lands. Anything the interface
changes is reported to the app through a Qt signal, which puts it back on the
GUI thread where it is safe to act on.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from jarvis.desktop_app.bridge import Bridge

logger = logging.getLogger(__name__)

#: The app's scheme and host. Together they form the interface's origin.
SCHEME = "ker"
HOST = "deck"
BASE_URL = f"{SCHEME}://{HOST}/"

_registered = False


def register_scheme() -> None:
    """Teach the web engine about ``ker://`` — must run before the QApplication.

    Marked secure and CORS-enabled so the page may use storage and ``fetch``;
    without those flags the engine treats it as a stranger and blocks both.
    """
    global _registered
    if _registered:
        return
    from PySide6.QtWebEngineCore import QWebEngineUrlScheme
    if QWebEngineUrlScheme.schemeByName(SCHEME.encode()).name():
        _registered = True
        return
    scheme = QWebEngineUrlScheme(SCHEME.encode())
    # Host syntax, not HostAndPort: there is no server behind this, and Qt
    # refuses to register a HostAndPort scheme without a real default port.
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    flags = (QWebEngineUrlScheme.Flag.SecureScheme
             | QWebEngineUrlScheme.Flag.LocalAccessAllowed
             | QWebEngineUrlScheme.Flag.CorsEnabled)
    fetch = getattr(QWebEngineUrlScheme.Flag, "FetchApiAllowed", None)
    if fetch is not None:  # Qt 6.6+: needed for fetch() on a custom scheme
        flags |= fetch
    scheme.setFlags(flags)
    QWebEngineUrlScheme.registerScheme(scheme)
    _registered = True


def install(profile, *, bridge: Bridge,
            pages: dict[str, Callable[[], str]],
            on_change: Callable[[set[str]], None] | None = None):
    """Serve ``pages`` and the bridge on ``profile``; returns the handler.

    ``pages`` maps a path ("/", "/login") to something that produces the HTML,
    read lazily so a page is only loaded when it is actually opened.
    """
    from PySide6.QtCore import (
        QBuffer,
        QByteArray,
        QIODevice,
        QObject,
        QRunnable,
        Qt,
        QThreadPool,
        Signal,
        Slot,
    )
    from PySide6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

    class _Signals(QObject):
        """Carries worker results back to the GUI thread."""

        finished = Signal(object, bytes, str)  # job, json payload, action
        changed = Signal(object)               # set of changed field names
        signed_in = Signal()                   # a login action just succeeded

    class _Action(QRunnable):
        """One bridge action, off the GUI thread."""

        def __init__(self, signals: _Signals, job, action: str,
                     payload: dict) -> None:
            super().__init__()
            self._signals = signals
            self._job = job
            self._action = action
            self._payload = payload

        @Slot()
        def run(self) -> None:
            result = bridge.handle(self._action, self._payload)
            data = json.dumps(result).encode("utf-8")
            self._signals.finished.emit(self._job, data, self._action)

    class InterfaceHandler(QWebEngineUrlSchemeHandler):
        """Answers page requests and bridge calls on the app's own scheme."""

        def __init__(self) -> None:
            super().__init__(profile)
            self.signals = _Signals()
            # Queued so the reply happens on the thread that owns the job.
            self.signals.finished.connect(self._reply_json,
                                          Qt.ConnectionType.QueuedConnection)
            if on_change is not None:
                self.signals.changed.connect(on_change,
                                             Qt.ConnectionType.QueuedConnection)
            self._pool = QThreadPool()
            self._pool.setMaxThreadCount(4)
            #: Jobs still waiting on a worker — dropped once answered.
            self._pending: set = set()

        # -- serving ---------------------------------------------------------

        def requestStarted(self, job) -> None:  # noqa: N802 - Qt naming
            path = job.requestUrl().path() or "/"
            if path.startswith("/call/"):
                self._start_action(job, path[len("/call/"):])
                return
            page = pages.get(path)
            if page is None:
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            try:
                html = page()
            except Exception as exc:  # noqa: BLE001 - show it, don't die
                logger.warning("Could not read page %s: %s", path, exc)
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
                return
            self._send(job, b"text/html", html.encode("utf-8"))

        def _start_action(self, job, action: str) -> None:
            from urllib.parse import parse_qs
            raw = parse_qs(job.requestUrl().query()).get("p", [""])[0]
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            self._pending.add(job)
            job.destroyed.connect(lambda *_: self._pending.discard(job))
            self._pool.start(_Action(self.signals, job, action, payload))

        def _reply_json(self, job, data: bytes, action: str) -> None:
            if job not in self._pending:
                return                      # the page went away meanwhile
            self._pending.discard(job)
            self._send(job, b"application/json", data)
            if action.startswith("login.") and bridge.signed_in:
                self.signals.signed_in.emit()

        def _send(self, job, mime: bytes, data: bytes) -> None:
            buffer = QBuffer(job)           # parented: outlives this call
            buffer.setData(QByteArray(data))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(QByteArray(mime), buffer)

    handler = InterfaceHandler()
    # Route config changes through the signal so the app hears about them on
    # the GUI thread, not on the worker that happened to run the save.
    bridge.set_on_change(None if on_change is None
                         else handler.signals.changed.emit)
    profile.installUrlSchemeHandler(SCHEME.encode(), handler)
    return handler
