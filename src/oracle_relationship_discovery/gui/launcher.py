"""Single-command production launcher for the local ReliFinder workbench."""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8741
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class GuiStartupError(OSError):
    """A concise, user-actionable GUI startup failure."""


def _browser_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def gui_url(host: str, port: int) -> str:
    return f"http://{_browser_host(host)}:{port}"


def _listening_socket(host: str, port: int) -> socket.socket:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise GuiStartupError(f"Cannot resolve GUI host {host!r}: {exc}") from None

    last_error: OSError | None = None
    for family, socktype, protocol, _, address in addresses:
        listener = socket.socket(family, socktype, protocol)
        try:
            listener.bind(address)
            listener.listen(2048)
            return listener
        except OSError as exc:
            last_error = exc
            listener.close()
    detail = f" ({last_error})" if last_error else ""
    raise GuiStartupError(
        f"Cannot start ReliFinder GUI on {host}:{port}; the address or port is unavailable{detail}. "
        "Stop the other process or choose another port with `--port`."
    ) from None


def _open_browser_when_ready(
    server: object,
    url: str,
    opener: Callable[[str], object],
    *,
    timeout_seconds: float = 30,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if bool(getattr(server, "started", False)):
            try:
                opener(url)
            except Exception as exc:  # noqa: BLE001 - browser failure must not stop the server.
                print(f"warning: could not open the browser automatically: {exc}", file=sys.stderr)
            return
        if bool(getattr(server, "should_exit", False)):
            return
        time.sleep(0.05)


def launch_gui(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    browser_opener: Callable[[str], object] = webbrowser.open,
) -> int:
    try:
        import uvicorn
    except ImportError:
        raise GuiStartupError(
            'GUI dependencies are not installed. Run `python -m pip install -e ".[gui]"`.'
        ) from None

    from oracle_relationship_discovery.gui.app import create_app

    app = create_app(serve_frontend=True)
    listener = _listening_socket(host, port)
    url = gui_url(host, port)
    if host not in LOOPBACK_HOSTS:
        print(
            f"warning: --host {host} may expose ReliFinder and its local Oracle session "
            "to other machines. Use a firewall and trusted network.",
            file=sys.stderr,
        )
    print(f"ReliFinder GUI: {url}")
    print("Press Ctrl+C to stop.")

    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="info", access_log=False)
    )
    browser_thread: threading.Thread | None = None
    if open_browser:
        browser_thread = threading.Thread(
            target=_open_browser_when_ready,
            args=(server, url, browser_opener),
            name="relifinder-browser",
            daemon=True,
        )
        browser_thread.start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        if browser_thread:
            browser_thread.join(timeout=0.2)
    return 0
