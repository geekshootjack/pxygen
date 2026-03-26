# Changelog

## 2026-03-26

### Merged milestone: Resolve refactor and pxygen rename

- Merged `codex/resolve-refactor-tdd` back into `main`.
- Renamed the project branding from `ProxyPilot` to `pxygen`.
- Renamed the internal Python package from `davinci_proxy_generator` to `pxygen`.
- Added the `pxygen` CLI entry point while keeping `proxy-generator` as a compatibility alias.

### Execution flow refactor

- Introduced explicit Resolve execution-plan models to separate planning from Resolve-side execution.
- Refactored Resolve orchestration into smaller helpers instead of one large function.
- Moved folder selection and filtering logic toward pure helpers that can be reused by future UI layers.
- Replaced remaining active-code `os.path` path handling with `pathlib` / pure path helpers.

### Resolve pipeline improvements

- Reduced Resolve API chatter by grouping imported clips in Python and moving them in batches by resolution and audio-group.
- Added sortable timeline names such as `0001-3840x2160` and `0002-3840x2160-multi-audio`.
- Bound render jobs to the current timeline explicitly before queueing.
- Restored clip-backed timeline creation after real Resolve testing showed empty-timeline append flows were unreliable.
- Fixed portrait proxy sizing so vertical footage scales to `1080x1920` instead of `608x1080`.
- Filtered `.jpg` and `.jpeg` files before Resolve import, including when a batch item is a directory.

### Logging and docs

- Replaced ad hoc `print()` output with structured logging and added `--log-level`.
- Updated English and Chinese README files plus usage docs to match the current CLI.
- Moved handoff/reference materials out of the repo root into `docs/`.
- Moved the legacy script into `legacy/`.

### Testing

- Expanded orchestration coverage with `tests/test_modes.py` and `tests/test_resolve_flow.py`.
- Added regression coverage for:
  - invalid resolution metadata
  - batch clip moves
  - timeline/render job binding
  - portrait proxy dimensions
  - JPG filtering in both file-list and directory-based import batches

### Verification snapshot

- `uv run pytest` -> `118 passed`
- `uv run ruff check src tests` -> `All checks passed!`

### Known caution

- Mocked tests are strong, but real DaVinci Resolve integration can still differ in timeline/render behavior. For high-confidence release validation, run an end-to-end test against a live Resolve instance and real footage.
