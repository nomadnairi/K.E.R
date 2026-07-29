# PyInstaller spec for the KER desktop app (PyInstaller >= 6).
#
# Local build (produces dist/KER[.exe] for the OS/arch you run it on):
#   pip install ".[gui]" pyinstaller
#   pyinstaller deploy/desktop/jarvis-desktop.spec
#
# CI builds set JARVIS_BUILD_NAME (e.g. KER-windows-amd64) so artifacts
# for every platform/arch can live side by side. PyInstaller cannot
# cross-compile — each target is built on a matching runner
# (.github/workflows/desktop-build.yml).
#
# The one-file binary bundles Python, Qt (PySide6, including WebEngine — the
# app's interface is a page), and the whole engine, so expect roughly
# 300-400 MB. User settings live outside the binary (%APPDATA%\JARVIS or
# ~/.config/jarvis), so it stays portable.

import os
from pathlib import Path

name = os.environ.get("JARVIS_BUILD_NAME", "KER")

a = Analysis(
    ["../../jarvis/desktop_app/__main__.py"],
    pathex=[str(Path(SPECPATH).resolve().parents[1])],
    binaries=[],
    # Ship the interface: the deck the app renders, its sign-in screen, and the
    # browser dashboard, which the bundled local API still serves at /app.
    datas=[
        ("../../jarvis/api/static/desktop.html", "jarvis/api/static"),
        ("../../jarvis/api/static/desktop_login.html", "jarvis/api/static"),
        ("../../jarvis/api/static/dashboard.html", "jarvis/api/static"),
        # The app's mark, used for the window and the tray at runtime.
        ("../../jarvis/desktop_app/assets/ker.ico", "jarvis/desktop_app/assets"),
        ("../../jarvis/desktop_app/assets/ker.png", "jarvis/desktop_app/assets"),
    ],
    hiddenimports=[
        "jarvis.desktop_app.app",
        "jarvis.desktop_app.engine_thread",
        "jarvis.desktop_app.webbridge",
        "jarvis.desktop_app.bridge",
        "jarvis.desktop_app.assets",
        "jarvis.integrations.telegram_channel",
        # The interface is a page, so the web view must be in the bundle.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        # The bundled local API (Command Deck) — uvicorn's dynamic imports.
        "uvicorn.loops.auto", "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.off", "uvicorn.logging", "websockets",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Drop modules we never import — smaller binary and lower memory at import
    # time. WebEngine and the Quick/QML stack it is built on are NOT excluded:
    # the app's whole interface is a page, and without them the built exe falls
    # back to plain widgets, which is exactly the bug this list once caused.
    excludes=[
        "tests", "tkinter", "PyQt5", "PySide2", "matplotlib", "IPython",
        "pytest", "pandas",
        "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtDesigner", "PySide6.QtTest", "PySide6.QtSql",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
        "PySide6.QtSerialPort",
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name=name,
    console=False,
    # Baked into the binary, so Windows Explorer and the taskbar show the mark
    # even before the app has started.
    icon=str(Path(SPECPATH).resolve().parents[1]
            / "jarvis" / "desktop_app" / "assets" / "ker.ico"),
    upx=False,
)
