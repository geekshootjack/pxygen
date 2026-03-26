"""DaVinci Resolve API interaction layer.

``DaVinciResolveScript`` is imported *lazily* inside :func:`process_files_in_resolve`
so that every other module in this package can be imported and tested without a live
Resolve instance.
"""
from __future__ import annotations

import itertools
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .plan import ResolveExecutionPlan, build_resolve_execution_plan


class ProxyGeneratorError(Exception):
    """Raised for expected, user-facing errors in proxy generation."""


@dataclass
class _ResolveContext:
    project_manager: object
    project: object
    media_storage: object
    media_pool: object
    root_folder: object


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
    return media_pool.AddSubFolder(parent, name)


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
    timeline = media_pool.CreateTimelineFromClips(timeline_name, clips)
    proxy_width, proxy_height = calculate_proxy_dimensions(resolution_str)
    timeline.SetSetting("useCustomSettings", "1")
    timeline.SetSetting("timelineResolutionWidth", proxy_width)
    timeline.SetSetting("timelineResolutionHeight", proxy_height)
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


def _classify_clips(media_pool, bin_folder, imported_clips: list) -> None:
    for clip in imported_clips:
        if clip.GetClipProperty("Type") == "Still":
            continue
        resolution = clip.GetClipProperty("Resolution")
        res_bin = _get_or_create_subfolder(media_pool, bin_folder, resolution)
        try:
            audio_tracks = int(clip.GetClipProperty("Audio Ch") or 0)
        except (ValueError, TypeError):
            audio_tracks = 0

        dest_bin = (
            _get_or_create_subfolder(media_pool, res_bin, "MultiAudio_5+")
            if audio_tracks > 4
            else res_bin
        )
        media_pool.MoveClips([clip], dest_bin)
        media_pool.SetCurrentFolder(bin_folder)


def _queue_render_jobs_for_bin(
    project,
    media_pool,
    bin_folder,
    target_dir: str,
    standard_preset: str,
    multi_audio_preset: str,
    counter,
    output: Callable[[str], None],
) -> None:
    for res_bin in bin_folder.GetSubFolderList():
        res_name = res_bin.GetName()
        standard_clips = res_bin.GetClipList()
        if standard_clips:
            output(f"  Render target (standard audio): {target_dir}")
            _add_render_job(
                project,
                media_pool,
                standard_clips,
                f"Video Resolution {res_name}   #{next(counter)}",
                res_name,
                standard_preset,
                target_dir,
            )

        for sub_bin in res_bin.GetSubFolderList():
            if sub_bin.GetName() == "MultiAudio_5+":
                multi_clips = sub_bin.GetClipList()
                if multi_clips:
                    output(f"  Render target (multi-audio):  {target_dir}")
                    _add_render_job(
                        project,
                        media_pool,
                        multi_clips,
                        f"Video Resolution {res_name} MultiAudio   #{next(counter)}",
                        res_name,
                        multi_audio_preset,
                        target_dir,
                    )


def _default_confirm_render(output: Callable[[str], None]) -> bool:
    output("\nAll render jobs added. Start rendering now? (y/n)")
    return input().strip().lower() == "y"


def execute_resolve_plan(
    plan: ResolveExecutionPlan,
    *,
    output: Callable[[str], None] = print,
    confirm_render: Callable[[], bool] | None = None,
) -> None:
    """Execute a pre-built Resolve plan."""
    context = _connect_to_resolve(plan.project_prefix)
    standard_preset, multi_audio_preset = _resolve_render_presets(plan.codec)

    if not plan.clean_image:
        context.project.LoadBurnInPreset("burn-in")

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
                    output(
                        f"  Warning: failed to import items from "
                        f"{batch.subfolder_key or footage_folder.footage_folder_name}"
                    )
                    continue

                _classify_clips(context.media_pool, bin_folder, imported_clips)
                _queue_render_jobs_for_bin(
                    context.project,
                    context.media_pool,
                    bin_folder,
                    batch.target_dir,
                    standard_preset,
                    multi_audio_preset,
                    counter,
                    output,
                )
            except Exception as exc:
                output(f"  Error processing items: {exc}")
                continue

    context.project_manager.SaveProject()
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
