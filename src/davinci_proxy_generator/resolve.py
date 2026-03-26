"""DaVinci Resolve API interaction layer.

``DaVinciResolveScript`` is imported *lazily* inside :func:`process_files_in_resolve`
so that every other module in this package can be imported and tested without a live
Resolve instance.
"""
from __future__ import annotations

import itertools
import os
from datetime import datetime
from pathlib import Path


class ProxyGeneratorError(Exception):
    """Raised for expected, user-facing errors in proxy generation."""


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
    """Create a Resolve project, import footage, and queue proxy render jobs.

    This function requires DaVinci Resolve to be running and the Resolve scripting
    environment variables to be set (``RESOLVE_SCRIPT_API``, ``RESOLVE_SCRIPT_LIB``,
    ``PYTHONPATH`` — see README).

    Args:
        organized_files: Mapping from footage-folder path to
            ``{subfolder_key: [item_paths]}`` as produced by the organise helpers.
        selected_footage_folders: Ordered list of keys from *organized_files* to
            process (allows callers to pre-filter or reorder).
        proxy_folder_path: Root output directory for generated proxies.
        subfolder_depth: Number of subfolder levels below the footage folder to
            recreate under the proxy root (``out_depth - in_depth``).
        is_directory_mode: Use ``'proxy'`` project prefix instead of
            ``'proxy_redo'``.
        clean_image: Skip loading the burn-in preset when ``True``.
        codec: ``'auto'`` (h265 for ≤4 audio channels, ProRes for >4),
            ``'prores'``, or ``'h265'`` / ``'hevc'`` / ``'265'``.
    """
    # Lazy import — only available when Resolve is running.
    import DaVinciResolveScript as dvr_script  # noqa: PLC0415

    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise ProxyGeneratorError(
            "Could not connect to DaVinci Resolve. "
            "Make sure Resolve is running before executing this script."
        )
    project_manager = resolve.GetProjectManager()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_prefix = "proxy" if is_directory_mode else "proxy_redo"
    project = project_manager.CreateProject(f"{project_prefix}_{timestamp}")

    media_storage = resolve.GetMediaStorage()
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    # Resolve render preset names
    codec_key = codec.lower()
    if codec_key in ("h265", "hevc", "265"):
        standard_preset = "FHD_h.265_420_8bit_5Mbps"
        multi_audio_preset = "FHD_h.265_420_8bit_5Mbps"
    elif codec_key == "prores":
        standard_preset = "FHD_prores_proxy"
        multi_audio_preset = "FHD_prores_proxy"
    else:  # auto: h265 for ≤4 audio channels, ProRes for >4
        standard_preset = "FHD_h.265_420_8bit_5Mbps"
        multi_audio_preset = "FHD_prores_proxy"

    if not clean_image:
        project.LoadBurnInPreset("burn-in")

    # Unique counter for timeline names within this project
    counter = itertools.count(1)

    def _get_or_create_subfolder(parent, name: str):
        for folder in parent.GetSubFolderList():
            if folder.GetName() == name:
                return folder
        return media_pool.AddSubFolder(parent, name)

    def _add_render_job(
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

    for footage_folder_path in selected_footage_folders:
        footage_folder_name = Path(footage_folder_path).name
        subfolders_dict = organized_files[footage_folder_path]

        print(f"\nProcessing footage folder: {footage_folder_name}")

        main_bin = media_pool.AddSubFolder(root_folder, footage_folder_name)

        for subfolder_key, items in sorted(subfolders_dict.items()):
            # Build the Resolve bin hierarchy and the proxy output directory
            if subfolder_key:
                bin_folder = main_bin
                for part in subfolder_key.split(os.sep):
                    bin_folder = _get_or_create_subfolder(bin_folder, part)
                subfolder_parts = subfolder_key.split(os.sep)
            else:
                bin_folder = main_bin
                subfolder_parts = []

            # Proxy output root for this subfolder
            proxy_target = Path(proxy_folder_path) / footage_folder_name
            if subfolder_parts:
                proxy_target = proxy_target.joinpath(*subfolder_parts)
            target_dir = str(proxy_target)

            try:
                imported_clips = media_storage.AddItemListToMediaPool(items)
                if not imported_clips:
                    print(f"  Warning: failed to import items from {subfolder_key or footage_folder_name}")
                    continue

                # Organise clips into resolution sub-bins; split multi-audio into a
                # dedicated "MultiAudio_5+" bin (ProRes preset for Adobe compatibility)
                for clip in imported_clips:
                    if clip.GetClipProperty("Type") == "Still":
                        continue
                    resolution = clip.GetClipProperty("Resolution")
                    res_bin = _get_or_create_subfolder(bin_folder, resolution)

                    try:
                        audio_tracks = int(clip.GetClipProperty("Audio Ch") or 0)
                    except (ValueError, TypeError):
                        audio_tracks = 0

                    dest_bin = (
                        _get_or_create_subfolder(res_bin, "MultiAudio_5+")
                        if audio_tracks > 4
                        else res_bin
                    )
                    media_pool.MoveClips([clip], dest_bin)
                    media_pool.SetCurrentFolder(bin_folder)

                # Queue render jobs — one per resolution bin (and one for MultiAudio)
                for res_bin in bin_folder.GetSubFolderList():
                    res_name = res_bin.GetName()

                    standard_clips = res_bin.GetClipList()
                    if standard_clips:
                        print(f"  Render target (standard audio): {target_dir}")
                        _add_render_job(
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
                                print(f"  Render target (multi-audio):  {target_dir}")
                                _add_render_job(
                                    multi_clips,
                                    f"Video Resolution {res_name} MultiAudio   #{next(counter)}",
                                    res_name,
                                    multi_audio_preset,
                                    target_dir,
                                )

            except Exception as exc:
                print(f"  Error processing items: {exc}")
                continue

    project_manager.SaveProject()
    print("\nAll render jobs added. Start rendering now? (y/n)")
    if input().strip().lower() == "y":
        project.StartRendering()
        print("Rendering started.")
    else:
        print("Project saved. Start rendering manually in DaVinci Resolve.")
