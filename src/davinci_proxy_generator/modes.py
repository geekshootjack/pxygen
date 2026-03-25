"""High-level entry points for the two operational modes.

Both modes ultimately call :func:`~davinci_proxy_generator.resolve.process_files_in_resolve`.
All DaVinci Resolve interaction is deferred to that function; everything here is
pure Python orchestration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .organize import (
    filter_folders_at_in_depth,
    organize_directory_mode_folders,
    organize_json_mode_files,
    parse_selection,
)
from .paths import path_parts
from .resolve import ProxyGeneratorError, process_files_in_resolve


def process_json_mode(
    json_path: str,
    proxy_path: str,
    dataset: int,
    in_depth: int,
    out_depth: int,
    *,
    clean_image: bool = False,
    filter_mode: str | None = None,
    filter_list: str | None = None,
    codec: str = "auto",
) -> None:
    """Re-generate missing proxies from a file-comparison JSON produced by File_Compare.

    Args:
        json_path: Path to the JSON comparison file.
        proxy_path: Root output directory for proxies.
        dataset: Which group to use from the comparison (1 or 2).
        in_depth: Absolute path depth of the footage-folder level.
        out_depth: Absolute path depth of the camera-reel level (≥ in_depth).
        clean_image: Skip burn-in overlay when ``True``.
        filter_mode: ``'select'`` or ``'filter'`` or ``None``.
        filter_list: Comma-separated folder names (only used when
            filter_mode == ``'filter'``).
        codec: Render codec selection (see
            :func:`~davinci_proxy_generator.resolve.process_files_in_resolve`).
    """
    if out_depth < in_depth:
        raise ValueError("Output depth must be ≥ input depth")
    if dataset not in (1, 2):
        raise ProxyGeneratorError(f"Invalid dataset value '{dataset}'. Must be 1 or 2.")

    try:
        comparison_data: dict = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProxyGeneratorError(f"Error reading JSON file: {exc}") from exc

    file_list: list[str] = list(comparison_data.get(f"files_only_in_group{dataset}", []))

    # Also include files with frame-count mismatches
    if "frame_count_mismatches" in comparison_data:
        path_key = f"path{dataset}"
        mismatch_files = [m[path_key] for m in comparison_data["frame_count_mismatches"]]
        file_list.extend(mismatch_files)
        print(f"Added {len(mismatch_files)} files from frame count mismatches (group {dataset})")

    if not file_list:
        raise ProxyGeneratorError(f"No files found in group{dataset}")

    print(f"Found {len(file_list)} files in group{dataset}")
    print("\n=== Configuration Summary ===")
    print(f"JSON file:    {json_path}")
    print(f"Dataset:      group{dataset}")
    print(f"Input depth:  {in_depth}")
    print(f"Output depth: {out_depth}")
    if file_list:
        example = file_list[0]
        parts = path_parts(example)
        if len(parts) >= in_depth:
            if in_depth == out_depth:
                print(f"Example:      {example}")
                print(f"Folder name:  {parts[in_depth - 1]}")
            else:
                print(f"Example:      {example}")
                print(f"Key fragment: {os.sep.join(parts[in_depth - 1:out_depth])}")

    organized = organize_json_mode_files(file_list, in_depth, out_depth)
    organized = filter_folders_at_in_depth(
        organized, in_depth, filter_mode, filter_list, show_full_path=True
    )

    if not organized:
        raise ProxyGeneratorError("No folders to process after filtering.")

    process_files_in_resolve(
        organized,
        list(organized),
        proxy_path,
        out_depth - in_depth,
        is_directory_mode=False,
        clean_image=clean_image,
        codec=codec,
    )


def process_directory_mode(
    footage_path: str,
    proxy_path: str,
    in_depth: int,
    out_depth: int,
    *,
    clean_image: bool = False,
    filter_mode: str | None = None,
    filter_list: str | None = None,
    codec: str = "auto",
) -> None:
    """Import footage directly from a folder hierarchy and generate proxies.

    Args:
        footage_path: Root footage directory.
        proxy_path: Root output directory for proxies.
        in_depth: Absolute path depth of the shooting-day folders.
        out_depth: Absolute path depth of the camera-reel folders (≥ in_depth).
        clean_image: Skip burn-in overlay when ``True``.
        filter_mode: ``'select'`` or ``'filter'`` or ``None``.
        filter_list: Comma-separated folder names (only used when
            filter_mode == ``'filter'``).
        codec: Render codec selection.
    """
    footage_dir = Path(footage_path)
    if not footage_dir.exists():
        raise ProxyGeneratorError(f"Footage folder does not exist: {footage_path}")
    if out_depth < in_depth:
        raise ValueError("Output depth must be ≥ input depth")

    footage_depth = len(path_parts(footage_path))
    print("\nDirectory mode:")
    print(f"  Footage:      {footage_path} (depth: {footage_depth})")
    print(f"  Proxy output: {proxy_path}")
    print(f"  Input depth:  {in_depth}")
    print(f"  Output depth: {out_depth}")

    # --- Walk to find all folders at exactly in_depth ---
    input_depth_folders: list[str] = []
    for root, dirs, _ in os.walk(footage_path):
        current_depth = len(path_parts(root))
        if current_depth == in_depth:
            input_depth_folders.append(root)
            dirs.clear()  # do not descend further
        elif current_depth > in_depth:
            dirs.clear()

    if not input_depth_folders:
        raise ProxyGeneratorError(
            f"No folders found at depth {in_depth} inside '{footage_path}'"
        )

    print(f"  Found {len(input_depth_folders)} folder(s) at depth {in_depth}")

    # --- For each input folder, collect target folders at out_depth ---
    # If a branch is shallower than out_depth, use the deepest available level.
    targets_by_input: dict[str, list[str]] = {}

    for input_folder in input_depth_folders:
        if in_depth == out_depth:
            targets_by_input[input_folder] = [input_folder]
            continue

        target_folders: list[str] = []
        max_depth_found = in_depth

        for root, dirs, _ in os.walk(input_folder):
            current_depth = len(path_parts(root))
            max_depth_found = max(max_depth_found, current_depth)
            if current_depth == out_depth:
                target_folders.append(root)
                dirs.clear()
            elif current_depth > out_depth:
                dirs.clear()

        if not target_folders and max_depth_found < out_depth:
            # Folder tree is shallower than requested — fall back to deepest level
            for root, _, _ in os.walk(input_folder):
                if len(path_parts(root)) == max_depth_found:
                    target_folders.append(root)

        targets_by_input[input_folder] = target_folders or [input_folder]

    # --- Selection / filtering at the input-depth level ---
    if filter_mode == "select":
        folder_paths = sorted(targets_by_input)
        print(f"\nFolders at depth {in_depth}:")
        for i, fp in enumerate(folder_paths, 1):
            count = len(targets_by_input[fp])
            print(f"  {i}. {fp}  ({count} sub-folder(s))")
        print("\nSelect folders to process (numbers, range like 2-4, or 'all'):")
        choice = input().strip()
        if choice.lower() != "all":
            selected = [folder_paths[i] for i in parse_selection(choice, len(folder_paths))]
            targets_by_input = {p: targets_by_input[p] for p in selected}

    elif filter_mode == "filter" and filter_list:
        filter_names = {n.strip() for n in filter_list.split(",")}
        filtered = {
            fp: targets
            for fp, targets in targets_by_input.items()
            if Path(fp).name in filter_names
        }
        if not filtered:
            available = sorted(Path(fp).name for fp in targets_by_input)
            print(f"Warning: No matching folders found for filter: {filter_list}")
            print(f"Available: {', '.join(available)}")
            raise ProxyGeneratorError(
                f"No matching folders found for filter: {filter_list}"
            )
        targets_by_input = filtered

    if not targets_by_input:
        raise ProxyGeneratorError("No folders to process after filtering.")

    all_target_folders: list[str] = [
        folder for targets in targets_by_input.values() for folder in targets
    ]
    print(f"\nTotal folders to process: {len(all_target_folders)}")

    if in_depth == out_depth:
        organized = organize_directory_mode_folders(all_target_folders, in_depth)
    else:
        organized = organize_json_mode_files(all_target_folders, in_depth, out_depth)

    if not organized:
        organized = {footage_path: {"": all_target_folders}}

    process_files_in_resolve(
        organized,
        list(organized),
        proxy_path,
        out_depth - in_depth,
        is_directory_mode=True,
        clean_image=clean_image,
        codec=codec,
    )
