"""High-level entry points for the two operational modes.

Both modes ultimately call :func:`~pxygen.resolve.process_files_in_resolve`.
All DaVinci Resolve interaction is deferred to that function; everything here is
pure Python orchestration.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from .organize import (
    describe_folders_at_in_depth,
    filter_folders_at_in_depth,
    organize_directory_mode_folders,
    organize_json_mode_files,
    parse_selection,
    select_folders_at_in_depth,
)
from .paths import format_path_parts, path_parts
from .plan import build_resolve_execution_plan
from .resolve import ProxyGeneratorError, execute_resolve_plan

logger = logging.getLogger(__name__)
OutputFn = Callable[[str], None]
InputFn = Callable[[], str]


def _stringify_table_cell(value: object) -> str:
    return str(value).replace("\n", " ")


def _render_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> list[str]:
    """Render a simple ASCII table for terminal output."""
    normalized_headers = tuple(_stringify_table_cell(header) for header in headers)
    normalized_rows = [
        tuple(_stringify_table_cell(cell) for cell in row)
        for row in rows
    ]
    widths = [
        max(
            len(normalized_headers[index]),
            *(len(row[index]) for row in normalized_rows),
        )
        for index in range(len(normalized_headers))
    ]

    def _format_row(row: tuple[str, ...]) -> str:
        cells = [f" {cell:<{widths[index]}} " for index, cell in enumerate(row)]
        return "|" + "|".join(cells) + "|"

    separator = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    lines = [separator, _format_row(normalized_headers), separator]
    lines.extend(_format_row(row) for row in normalized_rows)
    lines.append(separator)
    return lines


def _output_table(
    title: str,
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
    output: OutputFn,
) -> None:
    output(f"\n{title}")
    for line in _render_table(headers, rows):
        output(line)


def _print_folder_options(options, in_depth: int, output: OutputFn) -> None:
    rows = [
        (index, option.label, option.item_count)
        for index, option in enumerate(options, 1)
    ]
    _output_table(
        f"Folders at depth {in_depth}:",
        ("#", "Folder", "Items"),
        rows,
        output,
    )
    output("\nSelect folders to process (numbers, range like 2-4, or 'all'):")


def _read_selection_indices(
    options,
    in_depth: int,
    *,
    input_func: InputFn,
    output: OutputFn,
) -> list[int] | None:
    _print_folder_options(options, in_depth, output)
    choice = input_func().strip()
    if choice.lower() == "all":
        return None
    return parse_selection(choice, len(options))


def _iter_child_directories(path: Path) -> list[Path]:
    """Return child directories in deterministic order."""
    try:
        children = (child for child in path.iterdir() if child.is_dir())
        return sorted(children, key=lambda child: child.name)
    except OSError:
        return []


def _collect_directories_at_depth(root: Path, target_depth: int) -> list[Path]:
    """Collect directories exactly at *target_depth* without descending below them."""
    matches: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        current_depth = len(path_parts(current))
        if current_depth == target_depth:
            matches.append(current)
            continue
        if current_depth > target_depth:
            continue
        stack.extend(reversed(_iter_child_directories(current)))
    return matches


def _collect_directory_tree(root: Path) -> list[Path]:
    """Return *root* and all descendant directories in traversal order."""
    directories: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        directories.append(current)
        stack.extend(reversed(_iter_child_directories(current)))
    return directories


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
    input_func: InputFn | None = None,
    output: OutputFn | None = None,
    confirm_render: Callable[[], bool] | None = None,
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
            :func:`~pxygen.resolve.process_files_in_resolve`).
    """
    input_func = input_func or input
    output = output or logger.info

    if out_depth < in_depth:
        raise ValueError("Output depth must be ≥ input depth")
    if dataset not in (1, 2):
        raise ProxyGeneratorError(f"Invalid dataset value '{dataset}'. Must be 1 or 2.")

    try:
        comparison_data: dict = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProxyGeneratorError(f"Error reading JSON file: {exc}") from exc
    logger.debug("Loaded comparison JSON from %s", json_path)

    file_list: list[str] = list(comparison_data.get(f"files_only_in_group{dataset}", []))

    # Also include files with frame-count mismatches
    if "frame_count_mismatches" in comparison_data:
        path_key = f"path{dataset}"
        mismatch_files = [m[path_key] for m in comparison_data["frame_count_mismatches"]]
        file_list.extend(mismatch_files)
        output(f"Added {len(mismatch_files)} files from frame count mismatches (group {dataset})")
        logger.debug(
            "Merged %d frame-count mismatch file(s) into dataset %s",
            len(mismatch_files),
            dataset,
        )

    if not file_list:
        raise ProxyGeneratorError(f"No files found in group{dataset}")

    output(f"Found {len(file_list)} files in group{dataset}")
    summary_rows: list[tuple[object, ...]] = [
        ("JSON file", json_path),
        ("Dataset", f"group{dataset}"),
        ("Input depth", in_depth),
        ("Output depth", out_depth),
        ("File count", len(file_list)),
    ]
    if file_list:
        example = file_list[0]
        parts = path_parts(example)
        if len(parts) >= in_depth:
            if in_depth == out_depth:
                summary_rows.extend(
                    [
                        ("Example", example),
                        ("Folder name", parts[in_depth - 1]),
                    ]
                )
            else:
                fragment_parts = parts[in_depth - 1:out_depth]
                summary_rows.extend(
                    [
                        ("Example", example),
                        (
                            "Key fragment",
                            format_path_parts(
                                fragment_parts,
                                windows=":" in example[:3] or "\\" in example,
                            ),
                        ),
                    ]
                )
    _output_table("JSON mode:", ("Parameter", "Value"), summary_rows, output)

    organized = organize_json_mode_files(file_list, in_depth, out_depth)
    logger.debug("JSON mode produced %d top-level folder group(s)", len(organized))
    if filter_mode == "select":
        options = describe_folders_at_in_depth(organized, show_full_path=True)
        selected_indices = _read_selection_indices(
            options, in_depth, input_func=input_func, output=output
        )
        if selected_indices is not None:
            logger.debug("JSON mode selected folder indices: %s", selected_indices)
            organized = select_folders_at_in_depth(organized, selected_indices)
    elif filter_mode == "filter" and filter_list:
        organized = filter_folders_at_in_depth(organized, filter_list)
        if not organized:
            available_names = sorted(
                Path(key).name for key in organize_json_mode_files(file_list, in_depth, out_depth)
            )
            available = ", ".join(available_names)
            logger.warning("Warning: No matching folders found for filter: %s", filter_list)
            logger.warning("Available folders: %s", available)
        else:
            logger.debug("JSON mode filter %r kept %d folder group(s)", filter_list, len(organized))

    if not organized:
        raise ProxyGeneratorError("No folders to process after filtering.")

    plan = build_resolve_execution_plan(
        organized,
        list(organized),
        proxy_path,
        mode_name="json",
        clean_image=clean_image,
        codec=codec,
    )
    logger.debug(
        "Built JSON mode execution plan with %d footage folder(s)",
        len(plan.footage_folders),
    )
    execute_resolve_plan(plan, output=output, confirm_render=confirm_render)


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
    input_func: InputFn | None = None,
    output: OutputFn | None = None,
    confirm_render: Callable[[], bool] | None = None,
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
    input_func = input_func or input
    output = output or logger.info

    footage_dir = Path(footage_path)
    if not footage_dir.exists():
        raise ProxyGeneratorError(f"Footage folder does not exist: {footage_path}")
    if out_depth < in_depth:
        raise ValueError("Output depth must be ≥ input depth")

    footage_depth = len(path_parts(footage_path))
    # --- Walk to find all folders at exactly in_depth ---
    input_depth_folders = [
        str(path) for path in _collect_directories_at_depth(footage_dir, in_depth)
    ]
    logger.debug(
        "Directory mode discovered %d folder(s) at input depth %d",
        len(input_depth_folders),
        in_depth,
    )

    if not input_depth_folders:
        raise ProxyGeneratorError(
            f"No folders found at depth {in_depth} inside '{footage_path}'"
        )

    _output_table(
        "Directory mode:",
        ("Parameter", "Value"),
        [
            ("Footage", f"{footage_path} (depth: {footage_depth})"),
            ("Proxy output", proxy_path),
            ("Input depth", in_depth),
            ("Output depth", out_depth),
            ("Found folders", len(input_depth_folders)),
        ],
        output,
    )

    # --- For each input folder, collect target folders at out_depth ---
    # If a branch is shallower than out_depth, use the deepest available level.
    targets_by_input: dict[str, list[str]] = {}

    for input_folder in input_depth_folders:
        if in_depth == out_depth:
            targets_by_input[input_folder] = [input_folder]
            continue

        target_folders: list[str] = []
        max_depth_found = in_depth
        directory_tree = _collect_directory_tree(Path(input_folder))

        for root in directory_tree:
            current_depth = len(path_parts(root))
            max_depth_found = max(max_depth_found, current_depth)
            if current_depth == out_depth:
                target_folders.append(str(root))

        if not target_folders and max_depth_found < out_depth:
            # Folder tree is shallower than requested — fall back to deepest level
            target_folders = [
                str(root) for root in directory_tree if len(path_parts(root)) == max_depth_found
            ]
            logger.debug(
                "Falling back to deepest available level %d under %s",
                max_depth_found,
                input_folder,
            )

        targets_by_input[input_folder] = target_folders or [input_folder]
        logger.debug(
            "Input folder %s produced %d target folder(s)",
            input_folder,
            len(targets_by_input[input_folder]),
        )

    # --- Selection / filtering at the input-depth level ---
    if filter_mode == "select":
        folder_paths = sorted(targets_by_input)
        _output_table(
            f"Folders at depth {in_depth}:",
            ("#", "Folder", "Sub-folders"),
            [
                (index, folder_path, len(targets_by_input[folder_path]))
                for index, folder_path in enumerate(folder_paths, 1)
            ],
            output,
        )
        output("\nSelect folders to process (numbers, range like 2-4, or 'all'):")
        choice = input_func().strip()
        if choice.lower() == "all":
            selected_indices = None
        else:
            selected_indices = parse_selection(choice, len(folder_paths))
        if selected_indices is not None:
            selected = [folder_paths[i] for i in selected_indices]
            logger.debug("Directory mode selected folder paths: %s", selected)
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
            logger.warning("Warning: No matching folders found for filter: %s", filter_list)
            logger.warning("Available: %s", ", ".join(available))
            raise ProxyGeneratorError(
                f"No matching folders found for filter: {filter_list}"
            )
        targets_by_input = filtered
        logger.debug("Directory mode filter %r kept %d input folder(s)", filter_list, len(filtered))

    if not targets_by_input:
        raise ProxyGeneratorError("No folders to process after filtering.")

    all_target_folders: list[str] = [
        folder for targets in targets_by_input.values() for folder in targets
    ]
    output(f"\nTotal folders to process: {len(all_target_folders)}")

    if in_depth == out_depth:
        organized = organize_directory_mode_folders(all_target_folders, in_depth)
    else:
        organized = organize_json_mode_files(all_target_folders, in_depth, out_depth)

    if not organized:
        organized = {footage_path: {"": all_target_folders}}

    plan = build_resolve_execution_plan(
        organized,
        list(organized),
        proxy_path,
        mode_name="directory",
        clean_image=clean_image,
        codec=codec,
    )
    logger.debug(
        "Built directory mode execution plan with %d footage folder(s)",
        len(plan.footage_folders),
    )
    execute_resolve_plan(plan, output=output, confirm_render=confirm_render)
