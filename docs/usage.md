# CLI Reference

## Synopsis

```
proxy-generator (-f FOOTAGE | -j JSON) -p PROXY [options]
```

## Modes

### Directory Mode (`-f`)

Walks a footage folder tree, collects folders at the specified depth, imports them into DaVinci Resolve, and queues render jobs.

```sh
proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 5
```

### JSON Mode (`-j`)

Re-generates missing or incomplete proxies using file paths from a [File_Compare](https://github.com/UserProjekt/File_Compare) JSON result.

```sh
proxy-generator -j comparison.json -p /Volumes/SSD/Proxy -d 1 -i 4 -o 5
```

---

## Options

### Required

| Flag | Description |
|------|-------------|
| `-f, --footage PATH` | Footage root folder *(Directory mode)* |
| `-j, --json PATH` | File_Compare JSON file *(JSON mode)* |
| `-p, --proxy PATH` | Proxy output root folder |

### Depth Control

The depth values are **absolute** — counted from the filesystem root (including the drive letter on Windows).

| Flag | Default (macOS / other) | Description |
|------|-------------------------|-------------|
| `-i, --in-depth N` | 5 / 4 | Depth of the shooting-day folders |
| `-o, --out-depth N` | 5 / 4 | Depth of the camera-reel folders (≥ in-depth) |

**Example** — given the path `/Volumes/SSD/Footage/Day1/A001`:

| Depth | Component |
|-------|-----------|
| 1 | `Volumes` |
| 2 | `SSD` |
| 3 | `Footage` |
| 4 | `Day1` |
| 5 | `A001` |

So `-i 4 -o 5` means: group by Day (depth 4), include camera reels as subfolders (depth 5).

### Folder Selection *(mutually exclusive)*

| Flag | Description |
|------|-------------|
| `-s, --select` | Print a numbered list of folders and read a selection from stdin |
| `--filter NAMES` | Comma-separated folder names to include (e.g. `"Day1,Day2"`) |

**Interactive selection example:**

```
Folders at depth 4:
  1. /Volumes/SSD/Footage/Shooting_Day_1  (3 sub-folders)
  2. /Volumes/SSD/Footage/Shooting_Day_2  (2 sub-folders)
  3. /Volumes/SSD/Footage/Shooting_Day_3  (4 sub-folders)

Select folders to process (numbers, range like 2-4, or 'all'):
> 1,3
```

### JSON Mode Options

| Flag | Default | Description |
|------|---------|-------------|
| `-d, --dataset {1,2}` | `1` | Which group to use from the comparison JSON |

### Render Options

| Flag | Default | Description |
|------|---------|-------------|
| `-c, --clean-image` | off | Skip burn-in overlays (timecode + clip name) |
| `-C, --codec CODEC` | `auto` | Override render preset (see below) |

**Codec values:**

| Value | Preset used |
|-------|-------------|
| `auto` | H.265 for ≤ 4 audio channels; ProRes Proxy for > 4 |
| `h265` / `hevc` / `265` | `FHD_h.265_420_8bit_5Mbps` |
| `prores` | `FHD_prores_proxy` |

The `auto` default exists because Adobe Premiere cannot hardware-decode 4:2:0 8-bit H.265 files with more than 4 audio tracks (Sony XAVC-I). ProRes avoids this issue.

---

## Examples

```sh
# Single depth level (shooting-day folders only)
proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 4

# Two depth levels (shooting day + camera reel)
proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 5

# Force ProRes for all clips
proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 5 -C prores

# Clean proxies (no burn-in), specific days
proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 5 \
  -c --filter "Shooting_Day_3,Shooting_Day_4"

# JSON mode, group 2, interactive selection
proxy-generator -j comparison.json -p /Volumes/SSD/Proxy -d 2 -i 4 -o 5 --select
```

---

## DaVinci Resolve Presets

ProxyPilot requires three presets to be imported into Resolve before use.
Preset files are included in the `presets/` directory:

| Preset name | File | Used for |
|-------------|------|----------|
| `FHD_h.265_420_8bit_5Mbps` | `presets/FHD_h.265_420_8bit_5Mbps.xml` | Standard proxy render |
| `FHD_prores_proxy` | `presets/FHD_prores_proxy.xml` | Multi-audio proxy render |
| `burn-in` | `presets/burn-in.xml` | Timecode + clip name overlay |

To import: **DaVinci Resolve → Deliver → Render Settings → ⋯ → Import Preset**.

---

## Recovery from Crashes

The project is saved automatically before rendering starts. If Resolve crashes mid-render:

1. Reopen DaVinci Resolve.
2. Open the `proxy_YYYYMMDD_HHMMSS` project that was created.
3. Go to **Deliver** and restart the render queue.

---

## Legacy Positional Arguments

The original positional syntax is still supported for backward compatibility:

```sh
# Directory mode (positional)
proxy-generator /path/to/footage /path/to/proxy

# JSON mode (positional)
proxy-generator comparison.json /path/to/proxy
```
