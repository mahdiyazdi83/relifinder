from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oracle_relationship_discovery.cli import build_parser
from oracle_relationship_discovery.cli import main as cli_main
from oracle_relationship_discovery.gui.app import create_app
from oracle_relationship_discovery.gui.frontend import FrontendBuildError
from oracle_relationship_discovery.gui.launcher import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    GuiStartupError,
    _listening_socket,
    _open_browser_when_ready,
    gui_url,
    launch_gui,
)


def _frontend(tmp_path: Path) -> Path:
    frontend = tmp_path / "static"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text(
        '<!doctype html><script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('relifinder')", encoding="utf-8")
    return frontend


def test_gui_parser_defaults_and_options() -> None:
    defaults = build_parser().parse_args(["gui"])
    assert defaults.host == DEFAULT_HOST
    assert defaults.port == DEFAULT_PORT
    assert defaults.no_browser is False

    custom = build_parser().parse_args(
        ["gui", "--host", "localhost", "--port", "9123", "--no-browser"]
    )
    assert (custom.host, custom.port, custom.no_browser) == ("localhost", 9123, True)


def test_legacy_cli_commands_remain_available() -> None:
    parser = build_parser()
    assert parser.parse_args(["--config", "config.yaml", "analyze"]).command == "analyze"
    assert parser.parse_args(["export-erd", "--input", "run"]).command == "export-erd"


def test_invalid_gui_port_is_a_parser_error() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["gui", "--port", "70000"])


def test_missing_frontend_build_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(FrontendBuildError, match="scripts/build_gui.py"):
        create_app(serve_frontend=True, frontend_dir=tmp_path)


def test_production_spa_api_and_static_routing(tmp_path: Path) -> None:
    app = create_app(serve_frontend=True, frontend_dir=_frontend(tmp_path))
    with TestClient(app) as client:
        root = client.get("/")
        deep_link = client.get("/results/run-123/relationship-456")
        api = client.get("/api/health")
        missing_api = client.get("/api/not-a-route")
        asset = client.get("/assets/app.js")
        file_like = client.get("/private/config.yaml")

    assert root.status_code == deep_link.status_code == 200
    assert "<!doctype html>" in root.text
    assert "<!doctype html>" in deep_link.text
    assert api.json() == {"status": "ok", "application": "relifinder"}
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert asset.status_code == 200
    assert "javascript" in asset.headers["content-type"]
    assert file_like.status_code == 404


def test_lifecycle_closes_runtime_resources(tmp_path: Path) -> None:
    class RecordingSessions:
        clear_calls = 0

        def clear(self) -> None:
            self.clear_calls += 1

    sessions = RecordingSessions()
    app = create_app(
        sessions=sessions,  # type: ignore[arg-type]
        serve_frontend=True,
        frontend_dir=_frontend(tmp_path),
    )
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
    assert sessions.clear_calls == 1


def test_loopback_socket_and_port_collision() -> None:
    listener = _listening_socket(DEFAULT_HOST, 0)
    port = listener.getsockname()[1]
    try:
        with pytest.raises(GuiStartupError, match="another port"):
            _listening_socket(DEFAULT_HOST, port)
    finally:
        listener.close()


def test_cli_reports_port_collision_without_traceback(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    listener = _listening_socket(DEFAULT_HOST, 0)
    port = listener.getsockname()[1]
    try:
        assert cli_main(["gui", "--no-browser", "--port", str(port)]) == 2
    finally:
        listener.close()
    output = capsys.readouterr().err + caplog.text
    assert "choose another port" in output
    assert "Traceback" not in output


def test_browser_opens_only_after_server_is_ready() -> None:
    opened: list[str] = []
    server = SimpleNamespace(started=True, should_exit=False)
    _open_browser_when_ready(server, "http://127.0.0.1:8741", opened.append)
    assert opened == ["http://127.0.0.1:8741"]
    assert gui_url("0.0.0.0", 8741) == "http://127.0.0.1:8741"


def test_launcher_honors_no_browser_and_closes_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    class Listener:
        closed = False

        def close(self) -> None:
            self.closed = True

    listener = Listener()
    opened: list[str] = []

    class FakeServer:
        started = False
        should_exit = False

        def __init__(self, _config: object) -> None:
            pass

        def run(self, *, sockets: list[object]) -> None:
            assert sockets == [listener]
            self.started = True

    monkeypatch.setattr(
        "oracle_relationship_discovery.gui.launcher._listening_socket",
        lambda _host, _port: listener,
    )
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", FakeServer)

    assert launch_gui(open_browser=False, browser_opener=opened.append) == 0
    assert listener.closed is True
    assert opened == []
