# pxygen

**Automated proxy generation for DaVinci Resolve.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![中文](https://img.shields.io/badge/文档-中文-red)](README.zh.md)

pxygen imports your footage into DaVinci Resolve, organises it into bins that mirror your folder hierarchy, and queues proxy render jobs — all in one command.

## Features

- **Two modes** — import directly from a folder tree, or re-generate missing proxies from an [fcmp](https://github.com/geekshootjack/fcmp) JSON report
- **Smart codec selection** — H.265 for ≤ 4 audio channels, ProRes Proxy for > 4 (Adobe Premiere compatibility)
- **Folder filtering** — process specific shooting days interactively (`--select`) or by name (`--filter`)
- **Cross-platform** — Windows, macOS

## Requirements

- Python ≥ 3.10, **64-bit**, official python.org build (Resolve's scripting binding does not work with uv-managed Python)
- DaVinci Resolve ≥ 19.1.4 (pxygen launches it automatically if it isn't running)
- Resolve render presets: `fhd-h265-5mbps`, `fhd-prores-proxy`
- Resolve burn-in preset: `burn-in-vertical` (centered layout, fits landscape and portrait)

## Environment Setup

None needed for standard Resolve installs — pxygen probes the well-known scripting locations on macOS (standard and App Store Studio), Windows, and Linux, and configures `sys.path` and DLL lookup by itself.

Only if Resolve lives at a non-standard path, point pxygen at it:

```sh
RESOLVE_SCRIPT_API=<path to .../Developer/Scripting>
RESOLVE_SCRIPT_LIB=<path to fusionscript.dll / .so / .dylib>
```

## Installation

Install as a tool with [uv](https://docs.astral.sh/uv/) (recommended):

```sh
uv tool install git+https://github.com/geekshootjack/pxygen          # latest main
uv tool install git+https://github.com/geekshootjack/pxygen@v2.0.0   # pinned release
uv tool upgrade pxygen                                               # follow the installed ref
```

To switch to a different release, `uv tool upgrade` won't change refs — reinstall:

```sh
uv tool install --force git+https://github.com/geekshootjack/pxygen@v2.1.0
```

Or run once without installing:

```sh
uvx --from git+https://github.com/geekshootjack/pxygen pxygen -i ... -o ...
```

### Offline install (no GitHub access)

For machines that cannot reach GitHub: download the `.whl` from the [Releases page](https://github.com/geekshootjack/pxygen/releases) on any connected machine, copy it over (USB drive, LAN share), then:

```sh
uv tool install ./pxygen-3.0.0-py3-none-any.whl
uv tool install --force ./pxygen-4.0.0-py3-none-any.whl   # upgrade to a newer wheel
```

The machine still needs [uv](https://docs.astral.sh/uv/) and an official python.org build installed. For a complete from-zero offline bootstrap (Python + uv + pxygen + Resolve presets on a USB drive), see **[docs/installation.md](docs/installation.md)**.

For development:

```sh
git clone https://github.com/geekshootjack/pxygen.git
cd pxygen
uv sync --all-groups
uv run pxygen --help
```

## Quick Start

```sh
# Directory mode — import footage and generate proxies
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5

# JSON mode — re-generate missing proxies from an fcmp report
pxygen -i fcmp_report.json -o /Volumes/SSD/Proxy -g a -n 4 -d 5

# Process only specific shooting days
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5 \
  --filter Shooting_Day_2 Shooting_Day_3
```

A typical footage layout:

```
<project>/
├── Footage/
│   ├── <shooting_day>/          # 260710
│   │   └── <camera_type>/       # multicam, documentary
│   │       └── <camera_unit>/   # FX3#1, FX6#2
│   └── <...>/
└── Proxy/
    └── <shooting_day>/
```

## Documentation

Full CLI reference, all flags, and advanced examples: **[docs/usage.md](docs/usage.md)**

## License

[MIT](LICENSE) — fork of [DaVinci_Script_Proxy_Generator](https://github.com/UserProjekt/DaVinci_Script_Proxy_Generator) by User22.
