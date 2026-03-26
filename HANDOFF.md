# Agent Handoff Document — ProxyPilot

**Date:** 2026-03-26
**Repo:** `github.com/thomjiji/DaVinci_Script_Proxy_Generator` (rename to ProxyPilot pending)
**Current version:** 1.5.2
**Package name:** `davinci-proxy-generator`, entry point: `proxy-generator`

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
Converted the legacy single-file `Proxy_generator.py` into a proper UV-managed Python package.

- `pyproject.toml` — hatchling build backend, entry point `proxy-generator`, dev deps: pytest + ruff
- `.python-version` — pinned to `3.14`
- `python-preference = "only-system"` — **critical** (see Windows section below)
- `uv run proxy-generator` is the canonical way to run it

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

### 4. CLI (`proxy-generator --help`)

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

Legacy positional syntax (`proxy-generator <input> <output>`) still works for backward compatibility.

### 5. Windows Compatibility — Critical Finding

**Problem:** `uv run proxy-generator` crashed silently on Windows.

**Root cause:** `DaVinciResolveScript.py` loads `fusionscript.dll` as a Python C extension via `importlib.machinery.ExtensionFileLoader`. The crash occurs inside `PyInit_fusionscript`. python-build-standalone (what uv downloads by default) statically links the C runtime; `fusionscript.dll` dynamically links `VCRUNTIME140.dll`. Two separate heaps → native crash. No Python-level fix is possible.

**Fix:** `python-preference = "only-system"` in `pyproject.toml`. uv now uses the official system Python (python.org installer) transparently. `uv run proxy-generator` still works as a single command.

**macOS risk:** On a clean macOS with no system Python (only Apple's stub), this will fail. Homebrew Python or the python.org installer must be present. Not yet tested against a live Resolve instance on macOS.

### 6. Docs & Housekeeping

- `README.md` — rewritten with ProxyPilot branding (EN)
- `README.zh.md` — full Chinese translation
- `docs/usage.md` — complete CLI reference
- `CLAUDE.md` — project guidance for AI coding sessions
- `TODO.md` — tracks backlog items
- `LICENSE` — added thomjiji as copyright holder alongside original author
- `Proxy_generator.py` — legacy root script, kept until WebUI milestone validated

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
- `Proxy_generator.py` (legacy root script) to be removed once this milestone is validated

**Design constraint:** The refactored package was explicitly designed with this separation in mind. `cli.py` already separates argument parsing from business logic (`modes.py`). The WebUI should call `process_directory_mode` / `process_json_mode` directly, the same way `cli.py` does — no duplication of business logic.

---

## Remaining Backlog (from TODO.md)

- [ ] WebUI milestone (FastAPI + HTML/JS) — **the next big thing**
- [ ] Ruff format-on-edit hook (uv is set up, can be wired anytime with `uv run ruff format`)
- [ ] Integration tests (require live Resolve + test footage — needs a dedicated test machine)
- [ ] Rename GitHub repo to `ProxyPilot` + update description
- [ ] Update `pyproject.toml` author field
- [ ] Remove `Proxy_generator.py` after WebUI milestone
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
