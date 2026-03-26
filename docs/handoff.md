# Agent Handoff Document — pxygen

**Date:** 2026-03-26
**Repo:** `github.com/thomjiji/DaVinci_Script_Proxy_Generator`
**Current version:** 1.5.2
**Package name:** `pxygen`, primary entry point: `pxygen` (legacy alias: `proxy-generator`)

---

## What This Project Does

Automates footage import and proxy generation in DaVinci Resolve. Given a footage directory (or a JSON comparison file from [File_Compare](https://github.com/UserProjekt/File_Compare)), it:

1. Walks the folder hierarchy to find shooting-day and camera-reel folders at configurable depths
2. Connects to a running DaVinci Resolve instance via its scripting API
3. Creates a new Resolve project, imports footage into organised bins
4. Splits clips by resolution and audio channel count into separate render queues
5. Queues proxy render jobs (H.265 or ProRes Proxy at 1080p) and optionally starts rendering

---

## What Was Done in This Session

### 1. UV Project Setup
Converted the legacy single-file `legacy/proxy_generator_legacy.py` into a proper UV-managed Python package.

- `pyproject.toml` — hatchling build backend, entry points `pxygen` and `proxy-generator`, dev deps: pytest + ruff
- `.python-version` — pinned to `3.14`
- `python-preference = "only-system"` — **critical** (see Windows section below)
- `uv run pxygen` is the canonical way to run it

### 2. Package Structure (`src/` layout)

```
src/davinci_proxy_generator/
├── __init__.py        # __version__ = "1.5.2"
├── __main__.py
├── cli.py             # argparse entry point, dispatches to modes
├── modes.py           # process_directory_mode, process_json_mode
├── organize.py        # pure Python: path grouping, folder filtering, selection
├── paths.py           # pure Python: path cleaning, splitting, key building
└── resolve.py         # DaVinci Resolve API interaction (lazy import)
```

**Key design decision:** `DaVinciResolveScript` is imported *lazily* inside `process_files_in_resolve()` so all other modules can be imported and tested without a running Resolve instance.

### 3. Test Suite — 99 tests

| File | What it covers |
|------|----------------|
| `tests/test_paths.py` | `clean_path_input`, `path_parts`, `compute_key_path`, `is_json_file` |
| `tests/test_organize.py` | `parse_selection`, `organize_json_mode_files`, `organize_directory_mode_folders`, `filter_folders_at_in_depth` |
| `tests/test_resolve_pure.py` | `calculate_proxy_dimensions` |
| `tests/test_cli.py` | argparse flag parsing + dispatch logic (mocked modes) |

Run with: `uv run pytest`

### 4. CLI (`pxygen --help`)

All flags have both short and long forms:

| Short | Long | Description |
|-------|------|-------------|
| `-i` | `--input` | Footage folder **or** JSON file — mode auto-detected |
| `-o` | `--output` | Proxy output folder |
| `-n` | `--in-depth` | Depth of shooting-day folders |
| `-d` | `--out-depth` | Depth of camera-reel folders |
| `-g` | `--group` | JSON mode: comparison group 1 or 2 |
| `-s` | `--select` | Interactive folder selection |
| `-f` | `--filter` | Comma-separated folder name filter |
| `-c` | `--clean-image` | No burn-in overlays |
| `-k` | `--codec` | `auto` / `prores` / `h265` / `hevc` / `265` |

Legacy positional syntax (`pxygen <input> <output>`) still works for backward compatibility.

### 5. Windows Compatibility — Critical Finding

**Problem:** `uv run pxygen` crashed silently on Windows.

**Root cause:** `DaVinciResolveScript.py` loads `fusionscript.dll` as a Python C extension via `importlib.machinery.ExtensionFileLoader`. The crash occurs inside `PyInit_fusionscript`. python-build-standalone (what uv downloads by default) statically links the C runtime; `fusionscript.dll` dynamically links `VCRUNTIME140.dll`. Two separate heaps → native crash. No Python-level fix is possible.

**Fix:** `python-preference = "only-system"` in `pyproject.toml`. uv now uses the official system Python (python.org installer) transparently. `uv run pxygen` still works as a single command.

**macOS risk:** On a clean macOS with no system Python (only Apple's stub), this will fail. Homebrew Python or the python.org installer must be present. Not yet tested against a live Resolve instance on macOS.

### 6. Docs & Housekeeping

- `README.md` — rewritten with pxygen branding (EN)
- `README.zh.md` — full Chinese translation
- `docs/usage.md` — complete CLI reference
- `docs/handoff.md` — agent handoff and branch notes
- `tasks/todo.md` — active engineering task tracker
- `LICENSE` — added thomjiji as copyright holder alongside original author
- `legacy/proxy_generator_legacy.py` — legacy script kept as reference

---

## Current Architecture — Data Flow

```
CLI (cli.py)
  └─ clean_path_input()          # strips shell escapes, normalises Windows drive letter
  └─ is_json_file()              # auto-detect mode
  └─ process_directory_mode()    # or process_json_mode()
       └─ path_parts()           # cross-platform path splitting
       └─ compute_key_path()     # build grouping key (Windows: E:\ not E:)
       └─ organize_*()           # group files/folders by depth
       └─ filter_folders_at_in_depth()   # --select / --filter
       └─ process_files_in_resolve()
            └─ import DaVinciResolveScript  (lazy)
            └─ create Resolve project
            └─ import footage into bins
            └─ split by resolution + audio channels
            └─ queue render jobs (H.265 or ProRes @ 1080p)
            └─ optionally start rendering
```

### Depth model

`--in-depth` = absolute path depth of the shooting-day folder (the "input grouping level").
`--out-depth` = absolute path depth of the camera-reel folder (the "output subfolder level").

macOS default: 5. Windows default: 4 (drive letter counts as one component).

Example (macOS, depth 5):
```
/Volumes/SSD/Footage/Day1/CamA   ← out-depth 5
                    ^^^^^ ← in-depth 4 (shooting day)
```

---

## What Comes Next — WebUI Milestone

The agreed next milestone is a **local FastAPI + HTML/JS web UI** that replaces the CLI entirely for end users:

- Server starts in the background on launch, browser opens automatically
- Web form covers all current CLI flags (input path, output path, depths, codec, filter, etc.)
- Closing the browser tab does NOT stop the server
- Behaviour must be identical to the current CLI
- `legacy/proxy_generator_legacy.py` (legacy reference script) to be removed once this milestone is validated

**Design constraint:** The refactored package was explicitly designed with this separation in mind. `cli.py` already separates argument parsing from business logic (`modes.py`). The WebUI should call `process_directory_mode` / `process_json_mode` directly, the same way `cli.py` does — no duplication of business logic.

---

## Remaining Backlog (from `tasks/todo.md`)

- [ ] WebUI milestone (FastAPI + HTML/JS) — **the next big thing**
- [ ] Ruff format-on-edit hook (uv is set up, can be wired anytime with `uv run ruff format`)
- [ ] Integration tests (require live Resolve + test footage — needs a dedicated test machine)
- [ ] Rename GitHub repo to `pxygen` + update description
- [ ] Update `pyproject.toml` author field
- [ ] Remove `legacy/proxy_generator_legacy.py` after WebUI milestone
- [ ] Validate macOS `only-system` Python behaviour on a clean machine

---

## Environment Setup (for any developer or agent)

```bash
# macOS / Linux
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

# Windows (cmd)
set RESOLVE_SCRIPT_API=%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
set RESOLVE_SCRIPT_LIB=C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll
set PYTHONPATH=%PYTHONPATH%;%RESOLVE_SCRIPT_API%\Modules\
set PATH=%PATH%;C:\Program Files\Blackmagic Design\DaVinci Resolve
```

DaVinci Resolve must be running. Python must be the official python.org build (not python-build-standalone).

---

## Branch Handoff Addendum — `codex/resolve-refactor-tdd`

This addendum summarizes all commits currently on the feature branch relative to `origin/main`, plus the current unresolved issue encountered in live Resolve testing.

### Branch commit history

1. `ef5a617` `refactor(resolve): split execution flow and add planning layer`
   - Added internal planning dataclasses in `src/davinci_proxy_generator/plan.py`
   - Refactored `modes.py` to build execution plans before calling Resolve
   - Split `resolve.py` into smaller orchestration helpers
   - Added orchestration-heavy tests in `tests/test_modes.py` and `tests/test_resolve_flow.py`

2. `aec2099` `refactor(paths): replace os.path flows with pathlib`
   - Removed `os.path` / `os.sep` handling from active package code and tests
   - Standardized path handling on `pathlib`, `PureWindowsPath`, and `PurePosixPath`
   - Reworked directory traversal to use `Path`-driven helpers

3. `35d9150` `refactor(resolve): batch clip moves and rename timelines`
   - Reduced Resolve API chatter by grouping imported clips in Python and moving them in batches per `(resolution, audio-group)`
   - Reworked timeline names to sortable, lowercase, hyphenated names:
     - `0001-4096x2160`
     - `0002-4096x2160-multi-audio`

4. `dd88cbc` `fix(resolve): guard invalid clip resolution`
   - Added `_normalize_resolution()`
   - Invalid/blank `Resolution` clip properties are skipped with a warning instead of crashing
   - Prevented malformed timeline names like `0001-`

5. `b119ab8` `refactor(logging): replace print output with structured logging`
   - Replaced ad hoc `print()` output with `logging`
   - Added `--log-level` to CLI
   - `INFO` is the normal operational verbosity
   - `DEBUG` logs micro-operations inside planning and Resolve execution

6. `f3b1466` `fix(resolve): bind render jobs to current timeline`
   - Explicitly calls `project.SetCurrentTimeline(timeline)` before queueing render jobs
   - Added regression coverage for render-job/timeline association

7. `42e7aec` `fix(resolve): create empty timelines before appending clips`
   - Attempted to solve the real Resolve timeline sizing issue by:
     - creating empty timelines
     - applying custom timeline settings first
     - appending clips afterward
   - This looked valid in tests, but failed in real Resolve: timelines were created, but clips were not actually added

8. `f995510` `fix(resolve): restore clip-backed timeline creation`
   - Reverted the unreliable empty-timeline path
   - Returned to `CreateTimelineFromClips(...)`
   - Kept explicit current-timeline binding and timeline-setting verification logic

### Current unresolved issue

The branch still has an unresolved live-integration bug in DaVinci Resolve:

- Multiple generated timelines are still ending up as `1920x1080` in real Resolve, even when their names indicate different source group resolutions such as `3840x2160` and `2160x3840`.
- This problem is **not** explained by the warning:
  - `Warning: skipping clip with invalid resolution property: ''`
  - That warning only skips clips whose metadata is blank; it does not explain why valid timelines all collapse to FHD.
- The current code path does set:
  - `useCustomSettings = "1"`
  - `timelineResolutionWidth = proxy_width`
  - `timelineResolutionHeight = proxy_height`
  - and also binds the created timeline as the current timeline before queueing the render job.

### What was observed in live Resolve

- The branch correctly groups clips by source resolution and audio-track count.
- Timeline names are created correctly.
- Render jobs are queued.
- An earlier attempted fix using `CreateEmptyTimeline()` plus `AppendToTimeline()` was rejected by reality:
  - debug logs claimed clips were appended
  - in actual Resolve, the timelines were created but contained no clips
- After reverting to `CreateTimelineFromClips()`, timeline population behavior returned, but the custom timeline resolution issue still remained unresolved in live Resolve.

### Likely next investigation areas

The next agent should start from runtime verification inside a real Resolve session, not from unit-test-only reasoning. Highest-value checks:

1. Inspect the exact return values and read-back values for:
   - `timeline.SetSetting("useCustomSettings", "1")`
   - `timeline.SetSetting("timelineResolutionWidth", ...)`
   - `timeline.SetSetting("timelineResolutionHeight", ...)`
   - `timeline.GetSetting(...)`

2. Check whether `project.LoadRenderPreset(...)` is resetting timeline or output sizing state after custom timeline settings are applied.

3. Compare timeline settings vs project render settings before and after:
   - `SetCurrentTimeline(timeline)`
   - `LoadRenderPreset(...)`
   - `SetRenderSettings(...)`
   - `AddRenderJob()`

4. Verify whether Resolve requires project-level settings changes, or a different order of operations, for timeline dimensions to survive into queued render jobs.

### Important caution

Do **not** assume fake tests prove correct Resolve behavior here. The current test suite passes, but this specific issue is now known to be a real integration gap between mocks and DaVinci Resolve itself.
