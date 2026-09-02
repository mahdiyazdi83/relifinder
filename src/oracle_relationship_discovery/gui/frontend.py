"""Production frontend asset discovery and narrow SPA routing."""

from __future__ import annotations

from importlib.resources import files
from os import fspath
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class FrontendBuildError(OSError):
    """Raised when the packaged production frontend is unavailable or incomplete."""


def packaged_frontend_directory() -> Path:
    """Return the installed frontend directory without relying on the current cwd."""
    return Path(fspath(files("oracle_relationship_discovery.gui").joinpath("static")))


def resolve_frontend_directory(frontend_dir: Path | None = None) -> Path:
    directory = (frontend_dir or packaged_frontend_directory()).resolve()
    index = directory / "index.html"
    assets = directory / "assets"
    if not index.is_file() or not assets.is_dir():
        raise FrontendBuildError(
            "ReliFinder GUI assets are missing. Reinstall from a complete source checkout "
            "or ask a maintainer to run `python scripts/build_gui.py`."
        )
    return directory


def mount_frontend(app: FastAPI, frontend_dir: Path | None = None) -> Path:
    """Serve packaged Vite assets and route non-file browser paths to the SPA."""
    directory = resolve_frontend_directory(frontend_dir)
    index = directory / "index.html"
    app.mount(
        "/assets",
        StaticFiles(directory=directory / "assets", check_dir=True),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(index)

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend_route(frontend_path: str) -> FileResponse:
        # API paths retain API semantics, and file-like paths never map to arbitrary files.
        if frontend_path == "api" or frontend_path.startswith("api/") or "." in frontend_path:
            raise HTTPException(status_code=404)
        return FileResponse(index)

    return directory
