# Installation Checklist

Everything a workstation needs to run pxygen, including a full offline
bootstrap for machines that cannot reach GitHub (or the internet at all).

A machine needs four things:

| # | Component | Why |
|---|-----------|-----|
| 1 | Official python.org CPython ≥ 3.10, 64-bit | Resolve's `fusionscript` binding rejects uv-managed (python-build-standalone) interpreters |
| 2 | [uv](https://docs.astral.sh/uv/) | Installs and runs pxygen as a tool |
| 3 | pxygen itself | Via git URL (online) or `.whl` (offline) |
| 4 | DaVinci Resolve ≥ 19.1.4 with the three presets imported | The render/burn-in presets pxygen loads by name |

---

## Online install (machine can reach GitHub)

```sh
uv tool install git+https://github.com/geekshootjack/pxygen@vX.Y.Z
pxygen --help    # banner should show the pinned version
```

See [README](../README.md#installation) for upgrade/switch/uninstall commands.

---

## Offline bootstrap (machine cannot reach GitHub)

### On a connected machine, collect onto a USB drive:

1. **Python installer** — from https://www.python.org/downloads/
   (Windows: `python-3.x.x-amd64.exe`; macOS: `python-3.x.x-macos11.pkg`)
2. **uv standalone archive** — from https://github.com/astral-sh/uv/releases
   (Windows: `uv-x86_64-pc-windows-msvc.zip`; macOS: `uv-aarch64-apple-darwin.tar.gz`)
   — the install script needs network, the archive does not
3. **pxygen wheel** — `pxygen-X.Y.Z-py3-none-any.whl` from
   https://github.com/geekshootjack/pxygen/releases
4. **Resolve presets** — the three XML files under `presets/` in the repo
   (also inside the release's "Source code" archive; they are **not** in the wheel):
   `fhd-h265-5mbps.xml`, `fhd-prores-proxy.xml`, `burn-in-vertical.xml`

### On the target machine:

1. **Install Python** — run the installer; on Windows tick *Add python.exe to PATH*
2. **Install uv** — unzip the archive and put `uv.exe` (and `uvx.exe`) somewhere
   on `PATH` (e.g. `C:\Users\<you>\.local\bin`, creating it and adding to PATH if needed)
3. **Install pxygen**:
   ```sh
   uv tool install ./pxygen-X.Y.Z-py3-none-any.whl
   ```
   uv prints a note if its tool bin directory is not on PATH — follow it
   (`uv tool update-shell`), then open a new terminal
4. **Import the Resolve presets**:
   - `fhd-h265-5mbps.xml`, `fhd-prores-proxy.xml` — Deliver page → Render
     Settings → ⋯ → *Import Preset*
   - `burn-in-vertical.xml` — Workspace → Data Burn-In → preset menu → import
5. **Enable external scripting** — Resolve Preferences → System → General →
   *External scripting using* → **Local**

### Verify

```sh
pxygen --help            # banner shows the version, e.g. "pxygen v4.0.0"
uv tool list             # pxygen listed with the expected version
```

Then, with Resolve running, do a small real run against a test folder.

---

## Offline upgrade

Copy the new wheel over and force-reinstall:

```sh
uv tool install --force ./pxygen-X.Y.Z-py3-none-any.whl
```

Presets only need re-importing when they change (the Releases notes will say so).

---

## Troubleshooting

- **`pxygen` not found after install** — uv's tool bin dir is not on PATH;
  run `uv tool update-shell` and open a new terminal
- **Run aborts right after "Total folders to process" with no error** — the
  tool env is on a uv-managed interpreter; check with
  `uv tool list` / the env's `pyvenv.cfg`, reinstall with
  `uv tool install --force --no-managed-python ...`
- **"Could not connect to DaVinci Resolve"** — Resolve is not running, or
  external scripting is disabled (step 5 above)
- **Proxies render without burn-ins** — the `burn-in-vertical` preset was not
  imported (a warning appears in the log)
