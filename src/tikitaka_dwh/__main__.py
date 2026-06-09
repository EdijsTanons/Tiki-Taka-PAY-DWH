"""Entrypoint: finds a free port, launches Streamlit, opens the browser."""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

_LOCK_PORT = 55554


def _acquire_single_instance_lock() -> socket.socket | None:
    """Return a bound socket acting as a single-instance lock, or None if already running."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        lock.bind(("127.0.0.1", _LOCK_PORT))
        lock.listen(1)
        return lock
    except OSError:
        lock.close()
        return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _open_browser_when_ready(url: str, port: int, timeout: float = 60.0) -> None:
    """Poll until Streamlit is accepting connections, then open the browser.

    Runs in a daemon thread so it never blocks the main process.  The 60-second
    timeout guards against the thread hanging forever if Streamlit fails to start.
    """

    def _poll_and_open() -> None:
        deadline = time.monotonic() + timeout
        connected = False
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    connected = True
                    break
            except OSError:
                time.sleep(0.2)
        if connected:
            webbrowser.open(url)

    threading.Thread(target=_poll_and_open, daemon=True).start()


def main() -> None:
    from tikitaka_dwh.config import ensure_app_dirs
    from tikitaka_dwh.observability.logging import configure_logging
    from tikitaka_dwh.observability.sentry import init_sentry

    lock = _acquire_single_instance_lock()
    if lock is None:
        sys.exit(0)

    ensure_app_dirs()
    configure_logging()
    init_sentry()

    if getattr(sys, "frozen", False):
        # PyInstaller bundle: _MEIPASS is the _internal/ directory
        ui_app = Path(sys._MEIPASS) / "tikitaka_dwh" / "ui" / "app.py"  # type: ignore[attr-defined]
    else:
        ui_app = Path(__file__).parent / "ui" / "app.py"
    port = _free_port()
    url = f"http://localhost:{port}"

    _open_browser_when_ready(url, port)

    # Launch Streamlit in-process so this works correctly inside a PyInstaller
    # bundle where sys.executable is the bundled .exe, not python.exe.
    from streamlit import config as _st_config
    from streamlit.web import bootstrap

    # Set config options directly before starting the server.
    # flag_options dict is unreliable in the frozen bundle because Streamlit's
    # config may already be partially initialised by the time bootstrap.run()
    # calls load_config_options.
    _st_config.set_option("server.port", port)
    _st_config.set_option("server.headless", True)
    _st_config.set_option("server.enableCORS", False)
    _st_config.set_option("server.enableXsrfProtection", False)
    _st_config.set_option("browser.gatherUsageStats", False)
    # In a PyInstaller bundle, Streamlit incorrectly detects development mode
    # (its __file__ doesn't contain "site-packages"), which suppresses the
    # static file routes and causes 404 on every request.
    _st_config.set_option("global.developmentMode", False)

    bootstrap.run(str(ui_app), False, [], {})


if __name__ == "__main__":
    import traceback as _tb
    try:
        main()
    except Exception:
        _trace = _tb.format_exc()
        # Write to log if logging is configured
        try:
            import logging as _logging
            _logging.getLogger("tikitaka_dwh").critical("Fatal startup error:\n%s", _trace)
        except Exception:
            pass
        # Always write to a crash file next to the exe so it's visible
        try:
            import os as _os
            _crash_path = _os.path.join(
                _os.path.dirname(_os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)),
                "crash.log",
            )
            with open(_crash_path, "w") as _f:
                _f.write(_trace)
        except Exception:
            pass
        raise
