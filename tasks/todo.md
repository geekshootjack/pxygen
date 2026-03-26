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
- [x] Reproduce and lock the Resolve timeline resolution bug where queued jobs ignore the newly created timeline
- [x] Bind each render job to the created timeline before applying render settings and queueing
- [x] Verify mixed landscape/portrait timelines keep distinct proxy dimensions end-to-end
- [x] Lock a Resolve flow where timeline custom settings are applied before clips are appended
- [x] Switch render-job creation to empty timeline + verified settings + append clips
- [x] Re-verify that invalid-resolution warnings are isolated from valid timeline sizing

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
- Fixed Resolve render queue binding so each queued job explicitly targets its newly created timeline instead of silently inheriting the project's default current timeline.
- Added a regression test for mixed landscape/portrait clips to prove queued jobs preserve distinct proxy dimensions (`1920x1080` vs `608x1080`).
- Switched render job creation from `CreateTimelineFromClips()` to `CreateEmptyTimeline()` + verified custom settings + `AppendToTimeline()` so Resolve gets the timeline size before any clips are placed.
- Added runtime checks for timeline setting application so Resolve cannot silently queue a job after rejecting custom timeline dimensions.
- Verification:
  - `uv run pytest` -> 115 passed
  - `uv run ruff check src tests` -> All checks passed
