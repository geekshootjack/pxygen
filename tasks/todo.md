# Resolve Refactor TDD

## Checklist

- [x] Rename project branding and package metadata from ProxyPilot to pxygen
- [x] Update CLI help/examples to prefer `pxygen` while keeping old invocation compatibility if needed
- [x] Refresh README, Chinese README, usage doc, and handoff references to the new project name
- [x] Verify the rename via tests and lint, then commit as one change set
- [x] Rename the internal Python package from `davinci_proxy_generator` to `pxygen`
- [x] Update imports, tests, and package entry points for the internal rename
- [x] Re-run verification and auto-commit the internal package rename
- [x] Filter JPG/JPEG inputs before Resolve import, including when a batch item is a directory
- [x] Audit root-level files and decide keep/move/delete targets
- [x] Move reference and handoff docs out of the repo root
- [x] Remove duplicate top-level guidance/backlog files that already have canonical homes
- [x] Move the legacy script out of the repo root
- [x] Verify the cleaned root layout and run a lightweight regression check
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
- [x] Reproduce the real Resolve regression where empty timelines are created but clips are not appended
- [x] Switch render-job creation back to clip-backed timelines while preserving explicit timeline binding and setting verification
- [x] Re-verify timeline population and custom sizing behavior after removing the empty-timeline append path
- [x] Replace repetitive Resolve render-target lines with a shared rich table summary
- [x] Reuse one table-output helper across mode summaries and Resolve execution output
- [x] Verify the new render-job table output with tests and full regression checks
- [x] Decouple user-facing TUI rendering from the logging subsystem
- [x] Route default CLI output through a dedicated console presenter instead of `logger.info`
- [x] Restore logging to a standard detailed format and verify the separation with tests

## Notes

- Branch: `codex/resolve-refactor-tdd`
- Baseline before edits: existing pytest suite passed locally

## Review

- Added `tests/test_modes.py` and `tests/test_resolve_flow.py` to lock orchestration behavior.
- Introduced `src/pxygen/plan.py` with internal plan dataclasses used by modes and Resolve execution.
- Refactored `modes.py` to build execution plans and inject input/output hooks instead of mixing planning with direct Resolve calls.
- Refactored `resolve.py` into smaller private steps plus `execute_resolve_plan()`, while keeping `process_files_in_resolve()` as a compatibility wrapper.
- Removed terminal I/O from `organize.py` helpers by replacing interactive selection with pure option/selection helpers.
- Updated `README.md`, `README.zh.md`, and `docs/usage.md` to match the real CLI flags.
- Fixed Resolve render queue binding so each queued job explicitly targets its newly created timeline instead of silently inheriting the project's default current timeline.
- Added a regression test for mixed landscape/portrait clips to prove queued jobs preserve distinct proxy dimensions (`1920x1080` vs `608x1080`).
- Switched render job creation from `CreateTimelineFromClips()` to `CreateEmptyTimeline()` + verified custom settings + `AppendToTimeline()` so Resolve gets the timeline size before any clips are placed.
- Added runtime checks for timeline setting application so Resolve cannot silently queue a job after rejecting custom timeline dimensions.
- Reverted the empty-timeline append path after real Resolve showed it could create empty timelines without adding clips; render jobs now use `CreateTimelineFromClips()` again, with explicit current-timeline binding and setting verification kept in place.
- Reused a shared rich table helper across the CLI summaries and the Resolve execution layer, so repeated render-target lines now render as a compact `Render jobs` table with resolution, audio group, clip count, and target path columns.
- Decoupled terminal presentation from logging by adding a dedicated console presenter; user-facing tables, prompts, and progress text now go directly to stdout/stdin, while logging keeps a standard timestamped format and records operational events separately.
- Cleaned the repo root by moving handoff/reference material into `docs/`, moving the legacy script into `legacy/`, and deleting duplicate top-level `CLAUDE.md` / `TODO.md`.
- Renamed the project branding and package metadata from ProxyPilot / `davinci-proxy-generator` to `pxygen`, while keeping `proxy-generator` as a compatibility CLI alias.
- Fixed the JPG import gate so directory-mode batches are expanded to file paths before Resolve import, preventing JPG/JPEG files inside source folders from leaking into Resolve.
- Verification:
  - `uv run pytest` -> 118 passed
  - `uv run ruff check src tests` -> All checks passed
