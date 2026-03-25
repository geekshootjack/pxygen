# ProxyPilot — TODO

## In Progress

_nothing currently in progress_

## Up Next

- [ ] **WebUI milestone** — FastAPI + HTML/JS frontend
  - Local server launches on startup, browser opens automatically
  - Web form replaces all CLI flags (footage path, proxy path, depth, codec, filter, etc.)
  - Closing the browser tab does not stop the server
  - Behaviour must be identical to the current CLI

## Backlog

- [ ] Set up ruff format-on-edit hook (blocked: needs `uv run ruff format` — UV is now set up, hook can be wired any time)
- [ ] Add integration tests (requires live DaVinci Resolve instance — needs a test script that launches Resolve and runs against a test footage folder)
- [ ] Rename the GitHub repo to `ProxyPilot` and update the description
- [ ] Update `pyproject.toml` author field (currently still has original author)
- [ ] Remove `Proxy_generator.py` (legacy root script) once WebUI milestone is validated
- [ ] Consider `uv run proxy-generator` shell alias / wrapper script for convenience

## Done

- [x] UV project setup — `pyproject.toml`, `.python-version`, `uv.lock`, `.venv`
- [x] Unit test suite — 75 tests across `test_paths`, `test_organize`, `test_resolve_pure`
- [x] Refactor milestone — `src/davinci_proxy_generator/` package, pathlib, lazy Resolve import, `itertools.count`, entry point `proxy-generator`
- [x] Docs — README (EN + ZH), `docs/usage.md`, CLAUDE.md
- [x] License — added thomjiji as copyright holder
