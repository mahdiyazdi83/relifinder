from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_START_PATH = Path(__file__).resolve().parents[1] / "start.py"
_START_SPEC = importlib.util.spec_from_file_location("relifinder_source_start", _START_PATH)
assert _START_SPEC is not None and _START_SPEC.loader is not None
start = importlib.util.module_from_spec(_START_SPEC)
_START_SPEC.loader.exec_module(start)


def _fake_environment(directory: Path) -> Path:
    python = start.environment_python(directory)
    python.parent.mkdir(parents=True)
    python.touch()
    return python


def test_installation_marker_tracks_packaging_changes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    environment = tmp_path / "environment"
    repository.mkdir()
    (repository / "pyproject.toml").write_text("version = '1'", encoding="utf-8")
    _fake_environment(environment)

    fingerprint = start.installation_fingerprint(repository)
    assert start.installation_is_current(environment, fingerprint) is False
    start._write_marker(environment, fingerprint)
    assert start.installation_is_current(environment, fingerprint) is True

    (repository / "pyproject.toml").write_text("version = '2'", encoding="utf-8")
    assert (
        start.installation_is_current(environment, start.installation_fingerprint(repository))
        is False
    )


def test_environment_install_runs_only_when_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    environment = tmp_path / "environment"
    repository.mkdir()
    (repository / "pyproject.toml").write_text("[project]\nname='demo'", encoding="utf-8")
    python = _fake_environment(environment)
    commands: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        assert check is True
        commands.append((command, cwd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(start.subprocess, "run", fake_run)
    assert start.ensure_environment(repository, environment) == python
    assert commands == [
        (
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--quiet",
                "-e",
                ".[gui]",
            ],
            repository,
        )
    ]

    assert start.ensure_environment(repository, environment) == python
    assert len(commands) == 1


def test_main_forwards_options_to_the_official_gui_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    environment = tmp_path / "environment"
    python = _fake_environment(environment)
    captured: dict[str, object] = {}

    monkeypatch.setattr(start, "repository_root", lambda: repository)
    monkeypatch.setattr(start, "environment_directory", lambda _repository: environment)
    monkeypatch.setattr(start, "ensure_environment", lambda _repository, _directory: python)

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        captured.update(command=command, cwd=cwd, check=check)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(start.subprocess, "run", fake_run)
    assert start.main(["--no-browser", "--port", "9123"]) == 0
    assert captured == {
        "command": [
            str(python),
            "-m",
            "oracle_relationship_discovery",
            "gui",
            "--no-browser",
            "--port",
            "9123",
        ],
        "cwd": repository,
        "check": False,
    }
