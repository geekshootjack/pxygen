"""DaVinci Resolve API interaction layer.

``DaVinciResolveScript`` is imported *lazily* inside :func:`process_files_in_resolve`
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

logger = logging.getLogger(__name__)

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


def calculate_proxy_dimensions(resolution_str: str) -> tuple[str, str]:
    """Return *(proxy_width, proxy_height)* scaled to 1080p from a source resolution.

    The width is calculated to preserve the aspect ratio and rounded up to the
    nearest even number (required by most codecs).

    Args:
        resolution_str: Source resolution formatted as ``'WIDTHxHEIGHT'``
            (e.g. ``'4096x2160'``).

    Returns:
        A *(width, height)* tuple of strings (e.g. ``('1920', '1080')``).
    """
    width_s, height_s = resolution_str.split("x")
    aspect = int(width_s) / int(height_s)
    proxy_height = 1080
    proxy_width = round(proxy_height * aspect)
    if proxy_width % 2 == 1:
        proxy_width += 1
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


def _connect_to_resolve(project_prefix: str) -> _ResolveContext:
    """Connect to Resolve and create a fresh proxy project."""
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
        return "FHD_h.265_420_8bit_5Mbps", "FHD_h.265_420_8bit_5Mbps"
    if codec_key == "prores":
        return "FHD_prores_proxy", "FHD_prores_proxy"
    return "FHD_h.265_420_8bit_5Mbps", "FHD_prores_proxy"


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
    logger.debug(
        "Creating timeline %r for %d clip(s), resolution=%s, target=%s, preset=%s",
        timeline_name,
        len(clips),
        resolution_str,
        target_dir,
        render_preset,
    )
    proxy_width, proxy_height = calculate_proxy_dimensions(resolution_str)
    if hasattr(media_pool, "CreateEmptyTimeline") and hasattr(media_pool, "AppendToTimeline"):
        timeline = media_pool.CreateEmptyTimeline(timeline_name)
        if timeline is None:
            raise ProxyGeneratorError(f"Failed to create timeline {timeline_name!r}.")
        logger.debug("Created empty timeline %r before appending clips", timeline_name)
    else:
        timeline = media_pool.CreateTimelineFromClips(timeline_name, clips)
        if timeline is None:
            raise ProxyGeneratorError(f"Failed to create timeline {timeline_name!r} from clips.")

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
    if hasattr(media_pool, "AppendToTimeline"):
        appended_items = media_pool.AppendToTimeline(clips)
        if appended_items is None:
            raise ProxyGeneratorError(f"Failed to append clips to timeline {timeline_name!r}.")
        logger.debug("Appended %d clip(s) to timeline %r", len(clips), timeline_name)
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
    output: Callable[[str], None],
) -> list[_ClipGroup]:
    group_order: list[tuple[str, bool]] = []
    grouped_clips: dict[tuple[str, bool], list[object]] = {}
    destination_bins: dict[tuple[str, bool], object] = {}

    for clip in imported_clips:
        if clip.GetClipProperty("Type") == "Still":
            logger.debug("Skipping still image clip during Resolve classification")
            continue
        raw_resolution = clip.GetClipProperty("Resolution")
        resolution = _normalize_resolution(raw_resolution)
        if resolution is None:
            logger.warning(
                "Warning: skipping clip with invalid resolution property: %r",
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
        dest_bin = (
            _get_or_create_subfolder(media_pool, res_bin, "MultiAudio_5+")
            if is_multi_audio
            else res_bin
        )
        if key not in grouped_clips:
            group_order.append(key)
        destination_bins.setdefault(key, dest_bin)
        grouped_clips.setdefault(key, []).append(clip)

    clip_groups: list[_ClipGroup] = []
    for resolution, is_multi_audio in group_order:
        key = (resolution, is_multi_audio)
        clips = grouped_clips[key]
        dest_bin = destination_bins[key]
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
    output: Callable[[str], None],
) -> None:
    for clip_group in clip_groups:
        if clip_group.is_multi_audio:
            output(f"  Render target (multi-audio):  {target_dir}")
            render_preset = multi_audio_preset
        else:
            output(f"  Render target (standard audio): {target_dir}")
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


def _default_confirm_render(output: Callable[[str], None]) -> bool:
    output("\nAll render jobs added. Start rendering now? (y/n)")
    return input().strip().lower() == "y"


def execute_resolve_plan(
    plan: ResolveExecutionPlan,
    *,
    output: Callable[[str], None] | None = None,
    confirm_render: Callable[[], bool] | None = None,
) -> None:
    """Execute a pre-built Resolve plan."""
    output = output or logger.info
    context = _connect_to_resolve(plan.project_prefix)
    standard_preset, multi_audio_preset = _resolve_render_presets(plan.codec)
    logger.debug(
        (
            "Executing Resolve plan: mode=%s project_prefix=%s "
            "footage_folders=%d codec=%s clean_image=%s"
        ),
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
        main_bin = context.media_pool.AddSubFolder(
            context.root_folder, footage_folder.footage_folder_name
        )

        for batch in footage_folder.batches:
            bin_folder = _build_bin_folder(context.media_pool, main_bin, batch.bin_parts)
            try:
                imported_clips = context.media_storage.AddItemListToMediaPool(list(batch.items))
                if not imported_clips:
                    logger.warning(
                        "Warning: failed to import items from %s",
                        batch.subfolder_key or footage_folder.footage_folder_name,
                    )
                    continue
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
                    output,
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
                logger.error("  Error processing items: %s", exc)
                continue

    context.project_manager.SaveProject()
    logger.debug("Saved Resolve project")
    should_start_render = confirm_render or (lambda: _default_confirm_render(output))
    if should_start_render():
        context.project.StartRendering()
        output("Rendering started.")
    else:
        output("Project saved. Start rendering manually in DaVinci Resolve.")


def process_files_in_resolve(
    organized_files: dict[str, dict[str, list[str]]],
    selected_footage_folders: list[str],
    proxy_folder_path: str,
    subfolder_depth: int,
    *,
    is_directory_mode: bool = False,
    clean_image: bool = False,
    codec: str = "auto",
) -> None:
    """Backward-compatible wrapper that builds and executes a Resolve plan."""
    del subfolder_depth
    plan = build_resolve_execution_plan(
        organized_files,
        selected_footage_folders,
        proxy_folder_path,
        mode_name="directory" if is_directory_mode else "json",
        clean_image=clean_image,
        codec=codec,
    )
    execute_resolve_plan(plan)
