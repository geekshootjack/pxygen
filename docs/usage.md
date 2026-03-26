# CLI Reference

## Synopsis

```
pxygen -i INPUT -o OUTPUT [options]
```

## Modes

### Directory Mode

Walks a footage folder tree, collects folders at the specified depth, imports them into DaVinci Resolve, and queues render jobs.

```sh
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 4 -d 5
```

### JSON Mode

Re-generates missing or incomplete proxies using file paths from a [File_Compare](https://github.com/UserProjekt/File_Compare) JSON result.

```sh
pxygen -i comparison.json -o /Volumes/SSD/Proxy -g 1 -n 4 -d 5
```

---

## Options

### Required

| Flag | Description |
|------|-------------|
| `-i, --input PATH` | Footage root folder or File_Compare JSON file |
| `-o, --output PATH` | Proxy output root folder |

### Depth Control

Depth values now support a more intuitive relative interpretation:

- `0` means the input folder itself
- `1` means the first level below the input folder
- `2` means the second level below the input folder

Legacy absolute depths are still accepted for backward compatibility, so existing commands such as `-n 4 -d 5` continue to work.

| Flag | Default (macOS / other) | Description |
|------|-------------------------|-------------|
| `-n, --in-depth N` | 5 / 4 | Depth of the shooting-day folders |
| `-d, --out-depth N` | 5 / 4 | Depth of the camera-reel folders (≥ in-depth) |

**Example** — if your input folder is `/Volumes/SSD/Footage`:

| Depth | Meaning |
|-------|---------|
| `0` | `/Volumes/SSD/Footage` |
| `1` | `Day1` |
| `2` | `A001` |

So `-n 1 -d 2` means: group by Day, include camera reels as subfolders.
Legacy `-n 4 -d 5` still resolves to the same structure when used with that input root.

### Folder Selection *(mutually exclusive)*

| Flag | Description |
|------|-------------|
| `-s, --select` | Print a numbered list of folders and read a selection from stdin |
| `--filter NAMES` | Comma-separated folder names to include (e.g. `"Day1,Day2"`) |

**Interactive selection example:**

```
Folders at depth 4:
  1. /Volumes/SSD/Footage/Shooting_Day_1
  2. /Volumes/SSD/Footage/Shooting_Day_2
  3. /Volumes/SSD/Footage/Shooting_Day_3

Select folders to process (numbers, range like 2-4, or 'all'):
> 1,3
```

### JSON Mode Options

| Flag | Default | Description |
|------|---------|-------------|
| `-g, --group {1,2}` | `1` | Which group to use from the comparison JSON |

### Render Options

| Flag | Default | Description |
|------|---------|-------------|
| `-c, --clean-image` | off | Skip burn-in overlays (timecode + clip name) |
| `-k, --codec CODEC` | `auto` | Override render preset (see below) |

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
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 1 -d 1

# Two depth levels (shooting day + camera reel)
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 1 -d 2

# Force ProRes for all clips
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 1 -d 2 -k prores

# Clean proxies (no burn-in), specific days
pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy -n 1 -d 2 \
  -c --filter "Shooting_Day_3,Shooting_Day_4"

# JSON mode, group 2, interactive selection
pxygen -i comparison.json -o /Volumes/SSD/Proxy -g 2 -n 1 -d 2 --select
```

---

## DaVinci Resolve Presets

pxygen requires three presets to be imported into Resolve before use.
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
pxygen /path/to/footage /path/to/proxy

# JSON mode (positional)
pxygen comparison.json /path/to/proxy
```
