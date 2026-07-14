"""DaVinci Resolve API interaction layer.

``DaVinciResolveScript`` is imported lazily inside :func:`_connect_to_resolve`
so that every other module in this package can be imported and tested without a live
Resolve instance.
"""
from __future__ import annotations

import itertools
import logging
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import path_name
from .plan import ResolveExecutionPlan
from .presenter import (
    ConsolePresenter,
    OutputFn,
    UserAbort,
    display_width,
    pad_display,
    pad_display_right,
)

logger = logging.getLogger(__name__)

# Only video media is ever sent to Resolve's importer. Camera folders are
# full of sidecars (XML, BIN, BNP/IND/INP/INT, MHL, JPG stills) that waste
# import time at best and crash Resolve's decoder at worst.
_MEDIA_IMPORT_SUFFIXES = {
    ".avi",
    ".braw",
    ".crm",
    ".dng",
    ".m2ts",
    ".mov",
    ".mp4",
    ".mts",
    ".mxf",
    ".r3d",
}

# Centered layout (clip name top, timecode below it) that fits both landscape
# and portrait proxies; exported copy lives in presets/burn-in-vertical.xml
_BURN_IN_PRESET = "burn-in-vertical"

class PxygenError(Exception):
    """Raised for expected, user-facing errors in proxy generation."""


@dataclass
class _ResolveContext:
    project_manager: object
    project: object
    media_storage: object
    media_pool: object
    root_folder: object


@dataclass(frozen=True)
class _ClipGroup:
    resolution: str
    is_multi_audio: bool
    audio_channels: tuple[int, ...]
    clips: tuple[object, ...]


def calculate_proxy_dimensions(resolution_str: str) -> tuple[str, str]:
    """Return *(proxy_width, proxy_height)* scaled to a 1080 short edge.

    Landscape sources scale to ``1920x1080``-style proxies, while portrait
    sources scale to ``1080x1920``-style proxies. The resized dimension is
    rounded to the nearest even number (required by most codecs).

    Args:
        resolution_str: Source resolution formatted as ``'WIDTHxHEIGHT'``
            (e.g. ``'4096x2160'``).

    Returns:
        A *(width, height)* tuple of strings (e.g. ``('1920', '1080')`` or
        ``('1080', '1920')``).
    """
    width_s, height_s = resolution_str.split("x")
    source_width = int(width_s)
    source_height = int(height_s)

    if source_width >= source_height:
        scale = 1080 / source_height
    else:
        scale = 1080 / source_width

    proxy_width = round(source_width * scale)
    proxy_height = round(source_height * scale)

    if proxy_width % 2 == 1:
        proxy_width += 1
    if proxy_height % 2 == 1:
        proxy_height += 1

    return str(proxy_width), str(proxy_height)


def _normalize_resolution(resolution: str | None) -> str | None:
    """Return a canonical ``WIDTHxHEIGHT`` resolution string, or ``None``."""
    if not resolution:
        return None

    match = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", resolution)
    if not match:
        return None

    width, height = match.groups()
    return f"{width}x{height}"


def _setup_resolve_env() -> None:
    """Auto-detect the DaVinci Resolve scripting environment if not already configured.

    Probes well-known install locations per platform and injects the Modules
    directory into sys.path so that ``import DaVinciResolveScript`` works
    without the user having to set any environment variables manually.
    Skips detection when RESOLVE_SCRIPT_API is already set.
    """
    if os.environ.get("RESOLVE_SCRIPT_API"):
        modules_dir = Path(os.environ["RESOLVE_SCRIPT_API"]) / "Modules"
        if str(modules_dir) not in sys.path:
            sys.path.insert(0, str(modules_dir))
        return

    if sys.platform == "darwin":
        candidates = [
            (
                Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve")
                / "Developer/Scripting",
                Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
                / "Contents/Libraries/Fusion/fusionscript.so",
            ),
            (
                Path("/Applications/DaVinci Resolve Studio.app")
                / "Contents/Resources/Developer/Scripting",
                Path("/Applications/DaVinci Resolve Studio.app")
                / "Contents/Libraries/Fusion/fusionscript.so",
            ),
        ]
    elif sys.platform == "win32":
        programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        candidates = [
            (
                programdata / "Blackmagic Design" / "DaVinci Resolve"
                / "Support" / "Developer" / "Scripting",
                Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"),
            ),
        ]
    else:
        candidates = [
            (
                Path("/opt/resolve/Developer/Scripting"),
                Path("/opt/resolve/libs/Fusion/fusionscript.so"),
            ),
        ]

    for api_path, lib_path in candidates:
        modules_dir = api_path / "Modules"
        if modules_dir.exists():
            os.environ["RESOLVE_SCRIPT_API"] = str(api_path)
            os.environ["RESOLVE_SCRIPT_LIB"] = str(lib_path)
            sys.path.insert(0, str(modules_dir))
            logger.debug("Auto-configured Resolve scripting env from %s", api_path)
            return

    raise PxygenError(
        "找不到 DaVinci Resolve 脚本模块。请手动设置 RESOLVE_SCRIPT_API 和"
        " RESOLVE_SCRIPT_LIB —— 参见 README.md 的 Environment Setup 一节。"
    )


# Resolve cold-start is slow (splash, database, project manager); the
# scripting server only accepts connections once the UI is fully up.
_RESOLVE_LAUNCH_TIMEOUT_SECONDS = 120
_RESOLVE_POLL_INTERVAL_SECONDS = 2.0


def _resolve_executable() -> Path | None:
    """Locate the Resolve app next to the scripting library, if possible."""
    lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
    if not lib:
        return None
    lib_path = Path(lib)
    if sys.platform == "win32":
        exe = lib_path.parent / "Resolve.exe"
        return exe if exe.exists() else None
    if sys.platform == "darwin":
        for ancestor in lib_path.parents:
            if ancestor.suffix == ".app":
                return ancestor if ancestor.exists() else None
    return None


def _launch_resolve(executable: Path) -> None:
    """Start Resolve detached so it outlives this process."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", str(executable)])
    else:
        subprocess.Popen(
            [str(executable)],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )


def _probe_resolve_connection() -> bool:
    """Check from a throwaway subprocess whether Resolve accepts connections.

    fusionscript decides connectivity when the extension first loads — a
    process that imported it while Resolve was down can never connect, no
    matter how often scriptapp() is retried. Each probe subprocess loads the
    extension fresh, so it reflects the current state.
    """
    modules_dir = Path(os.environ["RESOLVE_SCRIPT_API"]) / "Modules"
    lines = ["import os, sys", f"sys.path.insert(0, {str(modules_dir)!r})"]
    if sys.platform == "win32":
        lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
        if lib:
            lines.append(f"os.add_dll_directory({str(Path(lib).parent)!r})")
    lines += [
        "import DaVinciResolveScript as dvr",
        "sys.exit(0 if dvr.scriptapp('Resolve') else 1)",
    ]
    try:
        completed = subprocess.run(
            [sys.executable, "-c", "\n".join(lines)],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Resolve probe subprocess failed: %s", exc)
        return False
    if completed.returncode not in (0, 1):
        logger.debug("Resolve probe stderr: %s", completed.stderr.decode(errors="replace"))
    return completed.returncode == 0


def _ensure_resolve_ready(output: OutputFn) -> None:
    """Make sure Resolve is up before fusionscript is loaded in this process."""
    if _probe_resolve_connection():
        return
    executable = _resolve_executable()
    if executable is None:
        raise PxygenError(
            "无法连接 DaVinci Resolve,也找不到它的可执行文件来启动。"
            "请手动启动 Resolve,并确认 Preferences → System → General 里"
            " 'External scripting using' 设为 Local。"
        )
    output("Resolve 未运行,正在启动...")
    logger.info("Launching Resolve from %s", executable)
    try:
        _launch_resolve(executable)
    except OSError as exc:
        raise PxygenError(f"启动 Resolve 失败:{exc}") from exc
    output(
        f"  等待 Resolve 接受脚本连接(最多 {_RESOLVE_LAUNCH_TIMEOUT_SECONDS} 秒)..."
    )
    deadline = time.monotonic() + _RESOLVE_LAUNCH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(_RESOLVE_POLL_INTERVAL_SECONDS)
        if _probe_resolve_connection():
            output("  Resolve 已就绪。")
            return
    raise PxygenError(
        f"Resolve 启动后 {_RESOLVE_LAUNCH_TIMEOUT_SECONDS} 秒内未接受脚本连接。"
        "请确认 Preferences → System → General 里 'External scripting using'"
        " 设为 Local,然后重新运行 pxygen。"
    )


def _needs_fresh_load() -> bool:
    return "DaVinciResolveScript" not in sys.modules


def _connect_to_resolve(project_prefix: str, output: OutputFn) -> _ResolveContext:
    """Connect to Resolve (launching it if needed) and create a fresh proxy project."""
    if _needs_fresh_load():
        _setup_resolve_env()

        # Python 3.8+ on Windows calls SetDefaultDllDirectories() at startup,
        # which disables PATH for DLL resolution. os.add_dll_directory() is the
        # documented replacement API — needed so fusionscript.dll can find its
        # sibling DLLs in the Resolve install directory.
        if sys.platform == "win32":
            resolve_lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
            if resolve_lib:
                os.add_dll_directory(str(Path(resolve_lib).parent))

        # Must happen BEFORE the import below: fusionscript can only connect
        # if Resolve is already up when the extension first loads.
        _ensure_resolve_ready(output)

    import DaVinciResolveScript as dvr_script  # noqa: PLC0415

    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise PxygenError(
            "无法连接 DaVinci Resolve。请确认 Resolve 正在运行,且"
            " Preferences → System → General 里 'External scripting using'"
            " 设为 Local。"
        )

    project_manager = resolve.GetProjectManager()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = project_manager.CreateProject(f"{project_prefix}_{timestamp}")
    media_storage = resolve.GetMediaStorage()
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()
    return _ResolveContext(project_manager, project, media_storage, media_pool, root_folder)


def _ensure_resolve_alive(context: _ResolveContext) -> None:
    """Raise if the Resolve connection has died (e.g. Resolve crashed).

    fusionscript remote objects don't raise when the host process dies —
    attribute lookups start returning None instead, which surfaces later as
    confusing "'NoneType' object is not callable" errors.
    """
    try:
        get_name = getattr(context.project, "GetName", None)
        alive = bool(get_name and get_name())
    except Exception:
        alive = False
    if not alive:
        raise PxygenError(
            "与 DaVinci Resolve 的连接已断开——它可能崩溃了。"
            "请重启 Resolve 并重新运行 pxygen 处理剩余文件夹。"
        )


def _resolve_render_presets(codec: str) -> tuple[str, str]:
    """Return the standard and multi-audio render preset names."""
    codec_key = codec.lower()
    if codec_key in ("h265", "hevc", "265"):
        return "fhd-h265-5mbps", "fhd-h265-5mbps"
    if codec_key == "prores":
        return "fhd-prores-proxy", "fhd-prores-proxy"
    return "fhd-h265-5mbps", "fhd-prores-proxy"


# Cache of (id(parent), name) -> folder to avoid re-probing Resolve on every
# lookup; each GetSubFolderList/GetName is a cross-process API round-trip.
_BinCache = dict


def _get_or_create_subfolder(media_pool, parent, name: str, cache: _BinCache):
    key = (id(parent), name)
    if key in cache:
        return cache[key]
    for folder in parent.GetSubFolderList():
        if folder.GetName() == name:
            cache[key] = folder
            return folder
    logger.debug("Creating subfolder %r under %r", name, parent.GetName())
    folder = media_pool.AddSubFolder(parent, name)
    cache[key] = folder
    return folder


def _build_timeline_name(index: int, resolution: str, *, is_multi_audio: bool) -> str:
    """Build a sortable timeline name for a render job."""
    base_name = f"{index:04d}-{resolution.lower()}"
    if is_multi_audio:
        return f"{base_name}-multi-audio"
    return base_name


def _build_bin_folder(media_pool, main_bin, bin_parts: tuple[str, ...], cache: _BinCache):
    bin_folder = main_bin
    for part in bin_parts:
        bin_folder = _get_or_create_subfolder(media_pool, bin_folder, part, cache)
    return bin_folder


def _filter_import_items(items: tuple[str, ...]) -> tuple[str, ...]:
    """Expand import items and keep only video media for Resolve import."""
    filtered_items: list[str] = []
    skipped_items: list[str] = []

    def _keep(path_str: str, suffix: str) -> None:
        if suffix.lower() in _MEDIA_IMPORT_SUFFIXES:
            filtered_items.append(path_str)
        else:
            skipped_items.append(path_str)

    for item in items:
        item_path = Path(item)
        if item_path.exists() and item_path.is_dir():
            for child in sorted(
                (path for path in item_path.rglob("*") if path.is_file()),
                key=lambda path: path.as_posix(),
            ):
                _keep(str(child), child.suffix)
            continue
        _keep(item, item_path.suffix)

    if skipped_items:
        logger.info(
            "Skipping %d non-media item(s) before Resolve import", len(skipped_items)
        )
        logger.debug("Skipped import items: %s", skipped_items)

    return tuple(filtered_items)


def _import_items(
    context: _ResolveContext,
    items: tuple[str, ...],
    output: OutputFn,
) -> list:
    """Import *items* one at a time.

    Per-item calls keep the TUI progress honest during long imports and
    let a failed import name the exact file instead of a batch range.
    """
    imported: list = []
    total = len(items)
    for index, item in enumerate(items, 1):
        clips = context.media_storage.AddItemListToMediaPool([item])
        if clips:
            imported.extend(clips)
        else:
            # Distinguish "nothing imported" from "Resolve died mid-import"
            _ensure_resolve_alive(context)
            logger.warning("Import returned no clips for %s", item)
        if total > 1:
            output(f"    已导入 {index}/{total}  {path_name(item)}")
    return imported


def _add_render_job(
    project,
    media_pool,
    clips: list,
    timeline_name: str,
    resolution_str: str,
    render_preset: str,
    target_dir: str,
) -> None:
    if not clips:
        return
    logger.info(
        "Queueing render job timeline=%s resolution=%s clips=%d target=%s preset=%s",
        timeline_name,
        resolution_str,
        len(clips),
        target_dir,
        render_preset,
    )
    proxy_width, proxy_height = calculate_proxy_dimensions(resolution_str)
    timeline = media_pool.CreateTimelineFromClips(timeline_name, clips)
    if timeline is None:
        raise PxygenError(f"无法从素材创建时间线 {timeline_name!r}。")
    logger.debug("Created timeline %r from %d clip(s)", timeline_name, len(clips))

    if hasattr(project, "SetCurrentTimeline"):
        if not project.SetCurrentTimeline(timeline):
            raise PxygenError(f"无法切换当前时间线到 {timeline_name!r}。")
        logger.debug("Set current timeline to %r before queueing render job", timeline_name)

    timeline_settings = {
        "useCustomSettings": "1",
        "timelineResolutionWidth": proxy_width,
        "timelineResolutionHeight": proxy_height,
    }
    for setting_name, setting_value in timeline_settings.items():
        if not timeline.SetSetting(setting_name, setting_value):
            raise PxygenError(
                f"无法将时间线 {timeline_name!r} 的设置 {setting_name!r}"
                f" 设为 {setting_value!r}。"
            )
    if hasattr(timeline, "GetSetting"):
        for setting_name, setting_value in timeline_settings.items():
            actual_value = timeline.GetSetting(setting_name)
            if actual_value != setting_value:
                raise PxygenError(
                    f"时间线 {timeline_name!r} 的设置 {setting_name!r} 未生效"
                    f"(期望 {setting_value!r},实际 {actual_value!r})。"
                )
    project.LoadRenderPreset(render_preset)
    project.SetRenderSettings(
        {
            "SelectAllFrames": True,
            "FormatWidth": int(proxy_width),
            "FormatHeight": int(proxy_height),
            "TargetDir": target_dir,
        }
    )
    project.AddRenderJob()


def _classify_clips(
    media_pool,
    bin_folder,
    imported_clips: list,
    bin_cache: _BinCache,
) -> list[_ClipGroup]:
    # First pass is pure classification: one GetClipProperty() round-trip per
    # clip (the no-arg form returns all properties at once). Bin folders are
    # resolved afterwards, once per group, instead of once per clip.
    # dict preserves insertion order (Python 3.7+); keys are (resolution, is_multi_audio)
    groups: dict[tuple[str, bool], tuple[list[object], set[int]]] = {}

    for clip in imported_clips:
        properties = clip.GetClipProperty() or {}
        if properties.get("Type") == "Still":
            logger.debug("Skipping still image clip during Resolve classification")
            continue
        raw_resolution = properties.get("Resolution")
        resolution = _normalize_resolution(raw_resolution)
        if resolution is None:
            logger.warning(
                "Skipping clip with invalid resolution property: %r",
                raw_resolution,
            )
            continue
        try:
            audio_tracks = int(properties.get("Audio Ch") or 0)
        except (ValueError, TypeError):
            audio_tracks = 0
        logger.debug("Clip classified as resolution=%s audio_tracks=%d", resolution, audio_tracks)

        is_multi_audio = audio_tracks > 4
        key = (resolution, is_multi_audio)
        if key not in groups:
            groups[key] = ([], set())
        groups[key][0].append(clip)
        groups[key][1].add(audio_tracks)

    clip_groups: list[_ClipGroup] = []
    for (resolution, is_multi_audio), (clips, channels) in groups.items():
        res_bin = _get_or_create_subfolder(media_pool, bin_folder, resolution, bin_cache)
        logger.debug(
            "Moving %d clip(s) into bin %r (multi_audio=%s)",
            len(clips),
            resolution,
            is_multi_audio,
        )
        media_pool.MoveClips(clips, res_bin)
        clip_groups.append(
            _ClipGroup(
                resolution=resolution,
                is_multi_audio=is_multi_audio,
                audio_channels=tuple(sorted(channels)),
                clips=tuple(clips),
            )
        )

    if clip_groups:
        media_pool.SetCurrentFolder(bin_folder)

    return clip_groups


def _queue_render_jobs_for_bin(
    project,
    media_pool,
    clip_groups: list[_ClipGroup],
    target_dir: str,
    standard_preset: str,
    multi_audio_preset: str,
    counter,
    output: OutputFn,
) -> None:
    jobs = [
        (
            clip_group,
            multi_audio_preset if clip_group.is_multi_audio else standard_preset,
        )
        for clip_group in clip_groups
    ]
    if jobs:
        output("  渲染任务:")
        rows = [
            (
                clip_group.resolution,
                "/".join(str(c) for c in clip_group.audio_channels) + "ch",
                f"{len(clip_group.clips)} 个片段",
                render_preset,
            )
            for clip_group, render_preset in jobs
        ]
        widths = [max(display_width(row[i]) for row in rows) for i in range(4)]
        for row in rows:
            output(
                "    "
                + pad_display(row[0], widths[0])
                + "  " + pad_display_right(row[1], widths[1])
                + "  " + pad_display_right(row[2], widths[2])
                + "  " + pad_display(row[3], widths[3])
                + "  ->  " + target_dir
            )

    for clip_group, render_preset in jobs:
        _add_render_job(
            project,
            media_pool,
            list(clip_group.clips),
            _build_timeline_name(
                next(counter),
                clip_group.resolution,
                is_multi_audio=clip_group.is_multi_audio,
            ),
            clip_group.resolution,
            render_preset,
            target_dir,
        )

def execute_resolve_plan(
    plan: ResolveExecutionPlan,
    *,
    output: OutputFn | None = None,
    confirm_render: Callable[[], bool] | None = None,
) -> None:
    """Execute a pre-built Resolve plan."""
    presenter = ConsolePresenter(output_func=output)
    output = presenter.show
    context = _connect_to_resolve(plan.project_prefix, output)
    standard_preset, multi_audio_preset = _resolve_render_presets(plan.codec)
    logger.info(
        "Executing Resolve plan mode=%s project_prefix=%s footage_folders=%d codec=%s",
        plan.mode_name,
        plan.project_prefix,
        len(plan.footage_folders),
        plan.codec,
    )

    if context.project.LoadBurnInPreset(_BURN_IN_PRESET):
        logger.debug("Loaded burn-in preset %r", _BURN_IN_PRESET)
    else:
        logger.warning(
            "Burn-in preset %r not found in Resolve; proxies will render"
            " without burn-ins. Import it from presets/burn-in-vertical.xml.",
            _BURN_IN_PRESET,
        )

    counter = itertools.count(1)
    bin_cache: _BinCache = {}

    total_folders = len(plan.footage_folders)
    for folder_index, footage_folder in enumerate(plan.footage_folders, 1):
        output(
            f"\n正在处理 {footage_folder.footage_folder_name}"
            f"({folder_index}/{total_folders})"
        )
        logger.info("Processing footage folder %s", footage_folder.footage_folder_name)
        _ensure_resolve_alive(context)
        main_bin = context.media_pool.AddSubFolder(
            context.root_folder, footage_folder.footage_folder_name
        )
        if main_bin is None:
            _ensure_resolve_alive(context)
            raise PxygenError(
                f"Resolve 无法创建媒体池 bin"
                f" {footage_folder.footage_folder_name!r}。"
            )

        for batch in footage_folder.batches:
            bin_folder = _build_bin_folder(
                context.media_pool, main_bin, batch.bin_parts, bin_cache
            )
            try:
                items_to_import = _filter_import_items(batch.items)
                if not items_to_import:
                    logger.info(
                        "Skipping batch %s because no importable items remain after JPG filtering",
                        batch.subfolder_key or footage_folder.footage_folder_name,
                    )
                    continue

                output(
                    f"  正在导入 {len(items_to_import)} 项到 Resolve(可能需要一些时间)..."
                )
                imported_clips = _import_items(context, items_to_import, output)
                if not imported_clips:
                    logger.warning(
                        "Failed to import items from %s",
                        batch.subfolder_key or footage_folder.footage_folder_name,
                    )
                    continue
                logger.info(
                    "Imported %d clip(s) for batch=%s target_dir=%s",
                    len(imported_clips),
                    batch.subfolder_key or footage_folder.footage_folder_name,
                    batch.target_dir,
                )
                logger.debug(
                    "Imported %d clip(s)/item(s) for batch %r under %s",
                    len(imported_clips),
                    batch.subfolder_key,
                    footage_folder.footage_folder_name,
                )

                clip_groups = _classify_clips(
                    context.media_pool,
                    bin_folder,
                    imported_clips,
                    bin_cache,
                )
                _queue_render_jobs_for_bin(
                    context.project,
                    context.media_pool,
                    clip_groups,
                    batch.target_dir,
                    standard_preset,
                    multi_audio_preset,
                    counter,
                    output,
                )
            except PxygenError:
                raise
            except Exception as exc:
                logger.error("Error processing items: %s", exc)
                # A dead Resolve surfaces as arbitrary exceptions on remote
                # calls; abort instead of failing every remaining batch.
                _ensure_resolve_alive(context)
                continue

        # Save after each folder so queued jobs survive a later Resolve crash
        context.project_manager.SaveProject()
        logger.debug(
            "Saved Resolve project after folder %s", footage_folder.footage_folder_name
        )

    logger.info("Saved Resolve project")
    should_start_render = confirm_render or (
        lambda: presenter.confirm("\n所有渲染任务已添加,现在开始渲染?(y/n/q)")
    )
    try:
        start_render = should_start_render()
    except UserAbort:
        raise UserAbort(
            "已中止——渲染任务仍保留在已保存的 Resolve 项目中。"
        ) from None
    if start_render:
        context.project.StartRendering()
        logger.info("Started Resolve rendering")
        output("渲染已开始。")
    else:
        logger.info("Render jobs queued; waiting for manual start in Resolve")
        output("项目已保存,请在 DaVinci Resolve 中手动开始渲染。")


