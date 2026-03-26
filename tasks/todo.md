# Resolve Refactor TDD

## Checklist

- [x] Confirm test baseline and branch setup
- [x] Add mode-layer tests for JSON and directory orchestration
- [x] Add Resolve orchestration tests for preset, import, bin, and render behavior
- [x] Introduce internal planning dataclasses between modes and Resolve execution
- [x] Extract Resolve execution into smaller private steps
- [x] Move interactive selection out of pure organization helpers
- [x] Align CLI help text and docs with the implemented flags
- [x] Run the full test suite and document results

## Notes

- Branch: `codex/resolve-refactor-tdd`
- Baseline before edits: existing pytest suite passed locally

## Review

- Added `tests/test_modes.py` and `tests/test_resolve_flow.py` to lock orchestration behavior.
- Introduced `src/davinci_proxy_generator/plan.py` with internal plan dataclasses used by modes and Resolve execution.
- Refactored `modes.py` to build execution plans and inject input/output hooks instead of mixing planning with direct Resolve calls.
- Refactored `resolve.py` into smaller private steps plus `execute_resolve_plan()`, while keeping `process_files_in_resolve()` as a compatibility wrapper.
- Removed terminal I/O from `organize.py` helpers by replacing interactive selection with pure option/selection helpers.
- Updated `README.md`, `README.zh.md`, and `docs/usage.md` to match the real CLI flags.
- Verification:
  - `uv run pytest` -> 109 passed
  - `uv run ruff check src tests` -> All checks passed
