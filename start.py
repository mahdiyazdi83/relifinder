"""Zero-setup source launcher for the ReliFinder GUI."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

MINIMUM_PYTHON = (3, 11)
BOOTSTRAP_VERSION = 1
VENV_OVERRIDE = "RELIFINDER_VENV"
MARKER_NAME = ".relifinder-bootstrap.json"


class BootstrapError(RuntimeError):
    """A concise first-run setup failure."""


def repository_root() -> Path:
    return Path(__file__).resolve().parent


def environment_directory(repository: Path) -> Path:
    override = os.environ.get(VENV_OVERRIDE)
    return Path(override).expanduser().resolve() if override else repository / ".venv"


def environment_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def installation_fingerprint(repository: Path) -> str:
    digest = hashlib.sha256()
    digest.update(f"bootstrap:{BOOTSTRAP_VERSION}\0".encode())
    digest.update(str(repository.resolve()).encode("utf-8"))
    digest.update(b"\0")
    digest.update((repository / "pyproject.toml").read_bytes())
    return digest.hexdigest()


def _read_marker(directory: Path) -> dict[str, object] | None:
    try:
        value = json.loads((directory / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def installation_is_current(directory: Path, fingerprint: str) -> bool:
    marker = _read_marker(directory)
    return bool(
        environment_python(directory).is_file()
        and marker
        and marker.get("fingerprint") == fingerprint
    )


def _write_marker(directory: Path, fingerprint: str) -> None:
    marker = directory / MARKER_NAME
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "bootstrap_version": BOOTSTRAP_VERSION,
                "fingerprint": fingerprint,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(marker)


def ensure_environment(repository: Path, directory: Path) -> Path:
    python = environment_python(directory)
    if not python.is_file():
        print(f"[ReliFinder] Creating a private Python environment in {directory} ...")
        venv.EnvBuilder(with_pip=True).create(directory)
    fingerprint = installation_fingerprint(repository)
    if not installation_is_current(directory, fingerprint):
        print("[ReliFinder] Installing the GUI for this source checkout ...")
        subprocess.run(
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
            cwd=repository,
            check=True,
        )
        _write_marker(directory, fingerprint)
    return python


def main(arguments: list[str] | None = None) -> int:
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        print(f"error: ReliFinder requires Python {required} or newer.", file=sys.stderr)
        return 2

    repository = repository_root()
    directory = environment_directory(repository)
    try:
        python = ensure_environment(repository, directory)
        return subprocess.run(
            [
                str(python),
                "-m",
                "oracle_relationship_discovery",
                "gui",
                *(arguments if arguments is not None else sys.argv[1:]),
            ],
            cwd=repository,
            check=False,
        ).returncode
    except subprocess.CalledProcessError as exc:
        print(
            f"error: ReliFinder setup failed with exit code {exc.returncode}. "
            "Check the installation output above and retry.",
            file=sys.stderr,
        )
        return exc.returncode or 1
    except (OSError, BootstrapError) as exc:
        print(f"error: ReliFinder could not start: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
