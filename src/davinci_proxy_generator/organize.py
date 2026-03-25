"""File and folder organisation by path depth.

All functions here are pure Python with no external dependencies.
"""
from __future__ import annotations

import os
from pathlib import Path

from .paths import compute_key_path, path_parts


def parse_selection(choice: str, max_num: int) -> list[int]:
    """Parse a selection string such as '1,3,5-7' into sorted 0-based indices.

    Numbers outside [1, max_num] are silently ignored.
    Invalid tokens are silently ignored.
    """
    indices: set[int] = set()
    for token in choice.split(","):
        token = token.strip()
        if "-" in token:
            try:
                start_s, end_s = token.split("-", 1)
                start, end = int(start_s.strip()), int(end_s.strip())
                for n in range(start, end + 1):
                    idx = n - 1
                    if 0 <= idx < max_num:
                        indices.add(idx)
            except ValueError:
                continue
        else:
            try:
                idx = int(token) - 1
                if 0 <= idx < max_num:
                    indices.add(idx)
            except ValueError:
                continue
    return sorted(indices)


def organize_json_mode_files(
    file_paths: list[str],
    in_depth: int,
    out_depth: int,
) -> dict[str, dict[str, list[str]]]:
    """Group file paths into ``{key_path: {subfolder_key: [file_paths]}}``

    *key_path* is the absolute path up to *in_depth* components.
    *subfolder_key* is the path fragment between *in_depth* and *out_depth*
    (empty string when depths are equal).
    Files whose depth is less than *in_depth* are skipped.
    """
    organized: dict[str, dict[str, list[str]]] = {}
    for file_path in file_paths:
        parts = path_parts(file_path)
        key_path = compute_key_path(parts, in_depth)
        if key_path is None:
            continue
        if out_depth > in_depth:
            subfolder_parts = parts[in_depth:out_depth]
            subfolder_key = os.sep.join(subfolder_parts) if subfolder_parts else ""
        else:
            subfolder_key = ""
        organized.setdefault(key_path, {}).setdefault(subfolder_key, []).append(file_path)
    return organized


def organize_directory_mode_folders(
    folders: list[str],
    in_depth: int,
) -> dict[str, dict[str, list[str]]]:
    """Group folder paths where in_depth == out_depth (no subfolder nesting).

    Each folder becomes its own key with a single empty-string subfolder entry.
    Folders shallower than *in_depth* are skipped.
    """
    organized: dict[str, dict[str, list[str]]] = {}
    for folder in folders:
        parts = path_parts(folder)
        key_path = compute_key_path(parts, in_depth)
        if key_path is None:
            continue
        organized.setdefault(key_path, {})[""] = [folder]
    return organized


def filter_folders_at_in_depth(
    organized_files: dict[str, dict[str, list[str]]],
    in_depth: int,
    filter_mode: str | None = None,
    filter_list: str | None = None,
    show_full_path: bool = False,
) -> dict[str, dict[str, list[str]]]:
    """Filter *organized_files* to a subset of top-level keys.

    Modes
    -----
    ``None``
        Return unchanged.
    ``'filter'``
        Keep only keys whose *name* (last component) appears in *filter_list*
        (comma-separated string).
    ``'select'``
        Print a numbered list and read a selection from stdin.
    """
    if not filter_mode:
        return organized_files

    # Build name → full_path mapping (last path component as display name)
    folder_map: dict[str, str] = {
        Path(key_path).name: key_path for key_path in organized_files
    }

    if filter_mode == "select":
        sorted_paths = sorted(organized_files)
        print(f"\nFolders available at depth {in_depth}:")
        for i, full_path in enumerate(sorted_paths, 1):
            file_count = sum(len(v) for v in organized_files[full_path].values())
            label = full_path if show_full_path else Path(full_path).name
            print(f"  {i}. {label} ({file_count} items)")
        print("\nSelect folders to process (numbers, range like 2-4, or 'all'):")
        choice = input().strip()
        if choice.lower() == "all":
            return organized_files
        selected = [sorted_paths[i] for i in parse_selection(choice, len(sorted_paths))]
        return {p: organized_files[p] for p in selected}

    if filter_mode == "filter" and filter_list:
        names = [n.strip() for n in filter_list.split(",")]
        filtered = {
            folder_map[n]: organized_files[folder_map[n]]
            for n in names
            if n in folder_map
        }
        if not filtered:
            print(f"Warning: No matching folders found for filter: {filter_list}")
            print(f"Available folders: {', '.join(sorted(folder_map))}")
        else:
            print(f"Filtering to folders: {', '.join(n for n in names if n in folder_map)}")
        return filtered

    return organized_files
