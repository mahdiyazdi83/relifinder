# Contributing to ReliFinder

Thank you for helping improve ReliFinder. Changes should preserve the project's priority order: database safety, correctness, explainability, performance, and coverage.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[gui,dev]"
cd gui/web
pnpm install --frozen-lockfile
```

See the README for platform-specific environment commands and the two-terminal Vite/FastAPI workflow.

## Before opening a pull request

From the repository root:

```bash
ruff check src tests scripts start.py
python -m compileall -q src scripts start.py
pytest
python scripts/build_gui.py --check
```

From `gui/web`:

```bash
pnpm lint
pnpm typecheck
pnpm test:run
pnpm build
pnpm test:e2e
```

Run `python scripts/build_gui.py` and commit the resulting package assets whenever frontend sources or GUI API contracts change.

## Data and security rules

- Use synthetic schemas, hosts, services, usernames, relationships, and screenshots in tests and documentation.
- Never commit real configuration, credentials, Oracle wallets, reports, logs, sampled values, or customer metadata.
- Preserve the central single-`SELECT` SQL guard and bounded validation defaults.
- Add focused tests for changes to scoring, SQL generation, path handling, credentials, or network exposure.
- Keep the legacy `oracle-relationship-discovery` CLI compatible unless a breaking release is explicitly planned.

Open an issue before a large architectural change. Keep pull requests focused and explain user-visible tradeoffs.