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
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .plan import ResolveExecutionPlan, build_resolve_execution_plan
from .presenter import ConsolePresenter, OutputFn
from .table_output import output_table

logger = logging.getLogger(__name__)

_SKIPPED_IMPORT_SUFFIXES = {".jpg", ".jpeg"}

class ProxyGeneratorError(Exception):
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
    clips: tuple[object, ...]
    dest_bin: object


def _audio_group_label(is_multi_audio: bool) -> str:
    return "multi-audio" if is_multi_audio else "standard"


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
                Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"),
                Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"),
            ),
            (
                Path("/Applications/DaVinci Resolve Studio.app/Contents/Resources/Developer/Scripting"),
                Path("/Applications/DaVinci Resolve Studio.app/Contents/Libraries/Fusion/fusionscript.so"),
            ),
        ]
    elif sys.platform == "win32":
        programdata = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        candidates = [
            (
                programdata / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Developer" / "Scripting",
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

    raise ProxyGeneratorError(
        "Could not find DaVinci Resolve scripting modules. "
        "Set RESOLVE_SCRIPT_API and RESOLVE_SCRIPT_LIB manually — "
        "see the Environment Setup section in README.md."
    )


def _connect_to_resolve(project_prefix: str) -> _ResolveContext:
    """Connect to Resolve and create a fresh proxy project."""
    _setup_resolve_env()

    # Python 3.8+ on Windows calls SetDefaultDllDirectories() at startup,
    # which disables PATH for DLL resolution. os.add_dll_directory() is the
    # documented replacement API — needed so fusionscript.dll can find its
    # sibling DLLs in the Resolve install directory.
    if sys.platform == "win32":
        resolve_lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
        if resolve_lib:
            os.add_dll_directory(str(Path(resolve_lib).parent))

    import DaVinciResolveScript as dvr_script  # noqa: PLC0415

    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise ProxyGeneratorError(
            "Could not connect to DaVinci Resolve. "
            "Make sure Resolve is running before executing this script."
        )

    project_manager = resolve.GetProjectManager()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = project_manager.CreateProject(f"{project_prefix}_{timestamp}")
    media_storage = resolve.GetMediaStorage()
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()
    return _ResolveContext(project_manager, project, media_storage, media_pool, root_folder)


def _resolve_render_presets(codec: str) -> tuple[str, str]:
    """Return the standard and multi-audio render preset names."""
    codec_key = codec.lower()
    if codec_key in ("h265", "hevc", "265"):
        return "fhd-h265-5mbps", "fhd-h265-5mbps"
    if codec_key == "prores":
        return "fhd-prores-proxy", "fhd-prores-proxy"
    return "fhd-h265-5mbps", "fhd-prores-proxy"


def _get_or_create_subfolder(media_pool, parent, name: str):
    for folder in parent.GetSubFolderList():
        if folder.GetName() == name:
            return folder
    logger.debug("Creating subfolder %r under %r", name, parent.GetName())
    return media_pool.AddSubFolder(parent, name)


def _build_timeline_name(index: int, resolution: str, *, is_multi_audio: bool) -> str:
    """Build a sortable timeline name for a render job."""
    base_name = f"{index:04d}-{resolution.lower()}"
    if is_multi_audio:
        return f"{base_name}-multi-audio"
    return base_name


def _build_bin_folder(media_pool, main_bin, bin_parts: tuple[str, ...]):
    bin_folder = main_bin
    for part in bin_parts:
        bin_folder = _get_or_create_subfolder(media_pool, bin_folder, part)
    return bin_folder


def _filter_import_items(items: tuple[str, ...]) -> tuple[str, ...]:
    """Expand import items and drop files that should never be sent to Resolve."""
    filtered_items: list[str] = []
    skipped_items: list[str] = []

    for item in items:
        item_path = Path(item)
        if item_path.exists() and item_path.is_dir():
            for child in sorted(
                (path for path in item_path.rglob("*") if path.is_file()),
                key=lambda path: path.as_posix(),
            ):
                if child.suffix.lower() in _SKIPPED_IMPORT_SUFFIXES:
                    skipped_items.append(str(child))
                    continue
                filtered_items.append(str(child))
            continue

        if item_path.suffix.lower() in _SKIPPED_IMPORT_SUFFIXES:
            skipped_items.append(item)
            continue
        filtered_items.append(item)

    if skipped_items:
        logger.info("Skipping %d JPG/JPEG item(s) before Resolve import", len(skipped_items))
        logger.debug("Skipped import items: %s", skipped_items)

    return tuple(filtered_items)


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
        raise ProxyGeneratorError(f"Failed to create timeline {timeline_name!r} from clips.")
    logger.debug("Created timeline %r from %d clip(s)", timeline_name, len(clips))

    if hasattr(project, "SetCurrentTimeline"):
        if not project.SetCurrentTimeline(timeline):
            raise ProxyGeneratorError(f"Failed to set current timeline to {timeline_name!r}.")
        logger.debug("Set current timeline to %r before queueing render job", timeline_name)

    timeline_settings = {
        "useCustomSettings": "1",
        "timelineResolutionWidth": proxy_width,
        "timelineResolutionHeight": proxy_height,
    }
    for setting_name, setting_value in timeline_settings.items():
        if not timeline.SetSetting(setting_name, setting_value):
            raise ProxyGeneratorError(
                f"Failed to set timeline setting {setting_name!r} to {setting_value!r} "
                f"for {timeline_name!r}."
            )
    if hasattr(timeline, "GetSetting"):
        for setting_name, setting_value in timeline_settings.items():
            actual_value = timeline.GetSetting(setting_name)
            if actual_value != setting_value:
                raise ProxyGeneratorError(
                    f"Timeline setting {setting_name!r} for {timeline_name!r} "
                    f"did not stick (expected {setting_value!r}, got {actual_value!r})."
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
) -> list[_ClipGroup]:
    # dict preserves insertion order (Python 3.7+); keys are (resolution, is_multi_audio)
    groups: dict[tuple[str, bool], tuple[list[object], object]] = {}

    for clip in imported_clips:
        if clip.GetClipProperty("Type") == "Still":
            logger.debug("Skipping still image clip during Resolve classification")
            continue
        raw_resolution = clip.GetClipProperty("Resolution")
        resolution = _normalize_resolution(raw_resolution)
        if resolution is None:
            logger.warning(
                "Skipping clip with invalid resolution property: %r",
                raw_resolution,
            )
            continue
        res_bin = _get_or_create_subfolder(media_pool, bin_folder, resolution)
        try:
            audio_tracks = int(clip.GetClipProperty("Audio Ch") or 0)
        except (ValueError, TypeError):
            audio_tracks = 0
        logger.debug("Clip classified as resolution=%s audio_tracks=%d", resolution, audio_tracks)

        is_multi_audio = audio_tracks > 4
        key = (resolution, is_multi_audio)
        if key not in groups:
            dest_bin = (
                _get_or_create_subfolder(media_pool, res_bin, "MultiAudio_5+")
                if is_multi_audio
                else res_bin
            )
            groups[key] = ([], dest_bin)
        groups[key][0].append(clip)

    clip_groups: list[_ClipGroup] = []
    for (resolution, is_multi_audio), (clips, dest_bin) in groups.items():
        logger.debug(
            "Moving %d clip(s) into %r for resolution=%s multi_audio=%s",
            len(clips),
            dest_bin.GetName(),
            resolution,
            is_multi_audio,
        )
        media_pool.MoveClips(clips, dest_bin)
        clip_groups.append(
            _ClipGroup(
                resolution=resolution,
                is_multi_audio=is_multi_audio,
                clips=tuple(clips),
                dest_bin=dest_bin,
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
    if clip_groups:
        output_table(
            "Render jobs:",
            ("Resolution", "Audio", "Clips", "Target"),
            [
                (
                    clip_group.resolution,
                    _audio_group_label(clip_group.is_multi_audio),
                    len(clip_group.clips),
                    target_dir,
                )
                for clip_group in clip_groups
            ],
            output,
        )

    for clip_group in clip_groups:
        if clip_group.is_multi_audio:
            render_preset = multi_audio_preset
        else:
            render_preset = standard_preset

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
    context = _connect_to_resolve(plan.project_prefix)
    standard_preset, multi_audio_preset = _resolve_render_presets(plan.codec)
    logger.info(
        "Executing Resolve plan mode=%s project_prefix=%s footage_folders=%d codec=%s clean_image=%s",
        plan.mode_name,
        plan.project_prefix,
        len(plan.footage_folders),
        plan.codec,
        plan.clean_image,
    )

    if not plan.clean_image:
        context.project.LoadBurnInPreset("burn-in")
        logger.debug("Loaded burn-in preset")

    counter = itertools.count(1)

    for footage_folder in plan.footage_folders:
        output(f"\nProcessing footage folder: {footage_folder.footage_folder_name}")
        logger.info("Processing footage folder %s", footage_folder.footage_folder_name)
        main_bin = context.media_pool.AddSubFolder(
            context.root_folder, footage_folder.footage_folder_name
        )

        for batch in footage_folder.batches:
            bin_folder = _build_bin_folder(context.media_pool, main_bin, batch.bin_parts)
            try:
                items_to_import = _filter_import_items(batch.items)
                if not items_to_import:
                    logger.info(
                        "Skipping batch %s because no importable items remain after JPG filtering",
                        batch.subfolder_key or footage_folder.footage_folder_name,
                    )
                    continue

                imported_clips = context.media_storage.AddItemListToMediaPool(list(items_to_import))
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
            except Exception as exc:
                logger.error("Error processing items: %s", exc)
                continue

    context.project_manager.SaveProject()
    logger.info("Saved Resolve project")
    should_start_render = confirm_render or (
        lambda: presenter.confirm("\nAll render jobs added. Start rendering now? (y/n)")
    )
    if should_start_render():
        context.project.StartRendering()
        logger.info("Started Resolve rendering")
        output("Rendering started.")
    else:
        logger.info("Render jobs queued; waiting for manual start in Resolve")
        output("Project saved. Start rendering manually in DaVinci Resolve.")


