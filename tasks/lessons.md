# Lessons

- Prefer keeping pure organization helpers free of terminal I/O so CLI and future WebUI layers can share them without extra mocking.
- When handling cross-platform paths, prefer `pathlib` pure path classes over mixing `Path` and `os.path`; concrete `Path` follows the host OS, while `PureWindowsPath` / `PurePosixPath` let us preserve the intended path semantics explicitly.
- Treat Resolve clip properties as untrusted external data: normalize and validate fields like `Resolution` before deriving timeline names or render settings, and skip bad values with explicit warnings instead of crashing.
- When queueing Resolve render jobs, model the API's "current timeline" behavior in tests and set the freshly created timeline explicitly before applying render settings; otherwise real Resolve can silently fall back to the project's default timeline resolution.
- Fake Resolve tests can miss real API behavior if they assume settings always stick; for timeline sizing, verify `SetSetting()` success and prefer a creation flow that applies custom settings before clips are appended, not after.
- Before hypothesizing a missing Resolve setting as the root cause, re-check the live code path and point to the exact lines; avoid suggesting a missing `useCustomSettings` call when it is already present.
- When real Resolve behavior contradicts a refactor that looked good in fakes, trust the integration result: in this codebase, `CreateEmptyTimeline()` + `AppendToTimeline()` is less reliable than `CreateTimelineFromClips()` and should not replace the proven path without a live end-to-end check.
- After multiple plausible fixes fail against real Resolve behavior, stop iterating blindly and produce a crisp handoff with commit history, observed runtime facts, and the exact unresolved integration gap instead of continuing speculative changes.
- Proxy sizing rules must preserve orientation: landscape proxies should target `1920x1080`, portrait proxies should target `1080x1920`, and tests should assert both exact dimensions instead of only checking for a positive even width.
- Respect the user's preference for automatic commits: once a modification batch is verified, commit it without making the user ask again; keep commits small so they remain easy to revert.
- Prefer short, neutral product names over overly polished branding; if a user rejects a name as awkward, propagate the rename consistently through docs, metadata, and CLI-facing text rather than leaving mixed branding behind.
- A project rename is not complete until the internal Python package path matches too; update module directories, imports, tests, and entry points together instead of stopping at README/pyproject branding.
- Import-boundary filters must match the actual payload shape: if directory mode hands folders to Resolve, filtering only file-path batches will not work. Cover both file inputs and directory inputs in tests.
- For terminal tables with mixed Chinese and ASCII text, stop hand-formatting widths. Use a maintained table-rendering library so wide-character alignment is handled by the renderer instead of by brittle string math.
