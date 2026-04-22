# pxygen

**Automated proxy generation for DaVinci Resolve.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![中文](https://img.shields.io/badge/文档-中文-red)](README.zh.md)

pxygen imports your footage into DaVinci Resolve, organises it into bins that mirror your folder hierarchy, and queues proxy render jobs — all in one command.

## Features

- **Two modes** — import directly from a folder tree, or re-generate missing proxies from a [File_Compare](https://github.com/UserProjekt/File_Compare) JSON
- **Smart codec selection** — H.265 for ≤ 4 audio channels, ProRes Proxy for > 4 (Adobe Premiere compatibility)
- **Burn-in overlays** — source clip name + timecode applied automatically; disable with `-c`
- **Folder filtering** — process specific shooting days interactively (`--select`) or by name (`--filter`)
- **Cross-platform** — macOS, Windows, Linux

## Requirements

- Python ≥ 3.9, **64-bit**
- DaVinci Resolve ≥ 19.1.4 (must be running)
- Resolve render presets: `fhd-h265-5mbps`, `fhd-prores-proxy`
- Resolve burn-in preset: `burn-in`

## Environment Setup

For standard Resolve installs, pxygen detects the scripting environment automatically — no manual setup needed.

If auto-detection fails (non-standard install path), set these variables manually before running pxygen:

<details>
<summary>macOS (standard install) — bash/zsh</summary>

```sh
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

<details>
<summary>macOS (App Store install) — bash/zsh</summary>

```sh
export RESOLVE_SCRIPT_API="/Applications/DaVinci Resolve Studio.app/Contents/Resources/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve Studio.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

<details>
<summary>Windows — PowerShell</summary>

```powershell
$env:RESOLVE_SCRIPT_API = "$env:PROGRAMDATA\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
$env:RESOLVE_SCRIPT_LIB = "C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
$env:PYTHONPATH = "$env:PYTHONPATH;$env:RESOLVE_SCRIPT_API\Modules\"
$env:PATH = "$env:PATH;C:\Program Files\Blackmagic Design\DaVinci Resolve"
```
</details>

<details>
<summary>Windows — Command Prompt</summary>

```bat
set RESOLVE_SCRIPT_API=%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting
set RESOLVE_SCRIPT_LIB=C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll
set PYTHONPATH=%PYTHONPATH%;%RESOLVE_SCRIPT_API%\Modules\
set PATH=%PATH%;C:\Program Files\Blackmagic Design\DaVinci Resolve
```
</details>

<details>
<summary>Linux — bash/zsh</summary>

```sh
export RESOLVE_SCRIPT_API="/opt/resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/opt/resolve/libs/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

<details>
<summary>Linux — fish</summary>

```fish
set -x RESOLVE_SCRIPT_API "/opt/resolve/Developer/Scripting"
set -x RESOLVE_SCRIPT_LIB "/opt/resolve/libs/Fusion/fusionscript.so"
set -x PYTHONPATH "$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```
</details>

## Installation

```sh
pip install git+https://github.com/thomjiji/pxygen.git
```

Or clone and install in editable mode:

```sh
git clone https://github.com/thomjiji/pxygen.git
cd pxygen
pip install -e .
```

## Quick Start

```sh
# Directory mode — import footage and generate proxies
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5

# JSON mode — re-generate missing proxies from a File_Compare result
pxygen -i comparison.json -o /Volumes/SSD/Proxy -g 1 -n 4 -d 5

# Process only specific shooting days
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5 \
  --filter "Shooting_Day_2,Shooting_Day_3"
```

A typical footage layout:

```
Production/
├── Footage/
│   ├── Shooting_Day_1/
│   │   ├── A001_C001/
│   │   └── B001_C001/
│   └── Shooting_Day_2/
└── Proxy/          ← output goes here
```

## Documentation

Full CLI reference, all flags, and advanced examples: **[docs/usage.md](docs/usage.md)**

## License

[MIT](LICENSE) — fork of [DaVinci_Script_Proxy_Generator](https://github.com/UserProjekt/DaVinci_Script_Proxy_Generator) by User22.
