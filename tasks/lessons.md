# Lessons

- Prefer keeping pure organization helpers free of terminal I/O so CLI and future WebUI layers can share them without extra mocking.
- When handling cross-platform paths, prefer `pathlib` pure path classes over mixing `Path` and `os.path`; concrete `Path` follows the host OS, while `PureWindowsPath` / `PurePosixPath` let us preserve the intended path semantics explicitly.
- Treat Resolve clip properties as untrusted external data: normalize and validate fields like `Resolution` before deriving timeline names or render settings, and skip bad values with explicit warnings instead of crashing.
