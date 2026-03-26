# Lessons

- Prefer keeping pure organization helpers free of terminal I/O so CLI and future WebUI layers can share them without extra mocking.
- When handling cross-platform paths, prefer `pathlib` pure path classes over mixing `Path` and `os.path`; concrete `Path` follows the host OS, while `PureWindowsPath` / `PurePosixPath` let us preserve the intended path semantics explicitly.
- Treat Resolve clip properties as untrusted external data: normalize and validate fields like `Resolution` before deriving timeline names or render settings, and skip bad values with explicit warnings instead of crashing.
- When queueing Resolve render jobs, model the API's "current timeline" behavior in tests and set the freshly created timeline explicitly before applying render settings; otherwise real Resolve can silently fall back to the project's default timeline resolution.
- Fake Resolve tests can miss real API behavior if they assume settings always stick; for timeline sizing, verify `SetSetting()` success and prefer a creation flow that applies custom settings before clips are appended, not after.
- Before hypothesizing a missing Resolve setting as the root cause, re-check the live code path and point to the exact lines; avoid suggesting a missing `useCustomSettings` call when it is already present.
- When real Resolve behavior contradicts a refactor that looked good in fakes, trust the integration result: in this codebase, `CreateEmptyTimeline()` + `AppendToTimeline()` is less reliable than `CreateTimelineFromClips()` and should not replace the proven path without a live end-to-end check.
