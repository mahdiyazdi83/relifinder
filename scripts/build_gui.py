"""Build and verify the production GUI assets committed inside the Python package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
WEB = REPOSITORY / "gui" / "web"
PACKAGE_GUI = REPOSITORY / "src" / "oracle_relationship_discovery" / "gui"
STATIC = PACKAGE_GUI / "static"
METADATA = "build-meta.json"


def source_files() -> list[Path]:
    explicit = [
        WEB / "index.html",
        WEB / "package.json",
        WEB / "pnpm-lock.yaml",
        WEB / "vite.config.ts",
        WEB / "eslint.config.js",
        *WEB.glob("tsconfig*.json"),
    ]
    frontend = [path for path in (WEB / "src").rglob("*") if path.is_file()]
    api = [
        path
        for path in PACKAGE_GUI.rglob("*.py")
        if "static" not in path.parts and path.name not in {"frontend.py", "launcher.py"}
    ]
    return sorted({path.resolve() for path in (*explicit, *frontend, *api) if path.is_file()})


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in source_files():
        digest.update(path.relative_to(REPOSITORY).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_build(directory: Path) -> None:
    if not (directory / "index.html").is_file():
        raise RuntimeError(f"missing production index: {directory / 'index.html'}")
    assets = directory / "assets"
    if not assets.is_dir() or not any(path.is_file() for path in assets.iterdir()):
        raise RuntimeError(f"missing production assets: {assets}")


def check_build() -> None:
    validate_build(STATIC)
    metadata_path = STATIC / METADATA
    if not metadata_path.is_file():
        raise RuntimeError(f"missing GUI build metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = source_fingerprint()
    if metadata.get("source_sha256") != expected:
        raise RuntimeError(
            "packaged GUI assets are stale; run `python scripts/build_gui.py` and commit the result"
        )
    print(f"GUI build is complete and current ({expected[:12]}).")


def run(command: list[str], *, cwd: Path = WEB) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def build() -> None:
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if not pnpm:
        raise RuntimeError("pnpm 11 is required for maintainers; enable Corepack and retry")
    run([pnpm, "install", "--frozen-lockfile"])
    run(
        [
            sys.executable,
            "-m",
            "oracle_relationship_discovery.gui.export_openapi",
            "gui/web/openapi.json",
        ],
        cwd=REPOSITORY,
    )
    run([pnpm, "exec", "openapi-typescript", "openapi.json", "-o", "src/api/schema.d.ts"])
    run([pnpm, "build"])
    # Hash after OpenAPI generation so the committed generated contract is covered.
    fingerprint = source_fingerprint()
    source_dist = WEB / "dist"
    validate_build(source_dist)

    temporary = PACKAGE_GUI / f".static-{uuid.uuid4().hex}"
    backup = PACKAGE_GUI / f".static-backup-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source_dist, temporary)
        (temporary / METADATA).write_text(
            json.dumps({"source_sha256": fingerprint}, indent=2) + "\n",
            encoding="utf-8",
        )
        validate_build(temporary)
        if STATIC.exists():
            STATIC.replace(backup)
        try:
            temporary.replace(STATIC)
        except Exception:
            if backup.exists() and not STATIC.exists():
                backup.replace(STATIC)
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup.exists():
            if not STATIC.exists():
                backup.replace(STATIC)
            else:
                shutil.rmtree(backup)
    check_build()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed assets without requiring Node.js or pnpm",
    )
    args = parser.parse_args()
    try:
        check_build() if args.check else build()
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
