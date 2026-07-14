"""High-level entry points for the two operational modes.

Both modes ultimately call :func:`~pxygen.resolve.execute_resolve_plan`.
All DaVinci Resolve interaction is deferred to that function; everything here is
pure Python orchestration.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .organize import (
    describe_folders_at_in_depth,
    filter_folders_at_in_depth,
    normalize_filter_names,
    organize_directory_mode_folders,
    organize_json_mode_files,
    parse_selection,
    select_folders_at_in_depth,
)
from .paths import format_path_parts, path_name, path_parts
from .plan import build_resolve_execution_plan
from .presenter import InputFn, OutputFn, output_kv, output_numbered, prompt_line
from .resolve import PxygenError, execute_resolve_plan

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DepthSpec:
    requested: int
    resolved: int


def _normalize_depth(root_depth: int, depth: int) -> _DepthSpec:
    """Interpret *depth* as a level relative to the input root."""
    if depth < 0:
        raise ValueError("深度值 (-n/-d) 必须 ≥ 0")
    resolved = root_depth + depth if root_depth > 0 else depth
    return _DepthSpec(requested=depth, resolved=resolved)


def _folder_labels(paths: list[str]) -> list[str]:
    """Return the distinguishing display label for each folder path.

    Leaf names are enough when they are unique; fall back to full paths
    when two folders share a name.
    """
    names = [path_name(path) for path in paths]
    if len(set(names)) != len(names):
        return list(paths)
    return names


_SELECTION_HINT = "\n输入编号如 '1 3 8',范围如 2-4,'all' 全选,'q' 退出"


def _print_folder_options(options, output: OutputFn) -> None:
    labels = _folder_labels([option.full_path for option in options])
    items = [
        f"{label}  ({option.item_count} 项)"
        for label, option in zip(labels, options)
    ]
    output_numbered(f"文件夹({len(options)} 个):", items, output)
    output(_SELECTION_HINT)


def _read_selection_indices(
    options,
    *,
    input_func: InputFn,
    output: OutputFn,
) -> list[int] | None:
    _print_folder_options(options, output)
    choice = prompt_line(input_func)
    if choice.lower() == "all":
        return None
    return parse_selection(choice, len(options))


_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({"_gsdata_"})


def _iter_child_directories(path: Path) -> list[Path]:
    """Return child directories in deterministic order, skipping system folders."""
    try:
        children = (
            child
            for child in path.iterdir()
            if child.is_dir() and child.name not in _EXCLUDED_DIR_NAMES
        )
        return sorted(children, key=lambda child: child.name)
    except OSError:
        return []


def _collect_directories_at_depth(root: Path, target_depth: int) -> list[Path]:
    """Collect directories exactly at *target_depth* without descending below them."""
    root_depth = len(path_parts(root))
    matches: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, root_depth)]
    while stack:
        current, current_depth = stack.pop()
        if current_depth == target_depth:
            matches.append(current)
            continue
        if current_depth > target_depth:
            continue
        stack.extend(
            (child, current_depth + 1)
            for child in reversed(_iter_child_directories(current))
        )
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
    side: str,
    in_depth: int,
    out_depth: int,
    *,
    filter_mode: str | None = None,
    filter_list: list[str] | None = None,
    codec: str = "auto",
    input_func: InputFn | None = None,
    output: OutputFn | None = None,
    confirm_render: Callable[[], bool] | None = None,
) -> None:
    """Re-generate missing proxies from a comparison JSON produced by fcmp.

    Args:
        json_path: Path to the fcmp JSON report.
        proxy_path: Root output directory for proxies.
        side: Which comparison side to use: ``'a'`` = ``unique_in_a``,
            ``'b'`` = ``unique_in_b``.
        in_depth: Folder level relative to the footage root recorded in the
            report (``group_a``/``group_b`` directories).
        out_depth: Batch level relative to the footage root recorded in the
            report.
        filter_mode: ``'select'`` or ``'filter'`` or ``None``.
        filter_list: Folder names to keep (only used when
            filter_mode == ``'filter'``).
        codec: Render codec selection (``auto``/``h265``/``prores``).
    """
    output = output or print
    input_func = input_func or input
    logger.info(
        "Running JSON mode json_path=%s proxy_path=%s side=%s in_depth=%d out_depth=%d",
        json_path,
        proxy_path,
        side,
        in_depth,
        out_depth,
    )

    if side not in ("a", "b"):
        raise PxygenError(f"无效的 side 值 '{side}',必须是 'a' 或 'b'。")

    try:
        comparison_data: dict = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise PxygenError(f"读取 JSON 文件失败:{exc}") from exc
    logger.debug("Loaded comparison JSON from %s", json_path)

    if "files_only_in_group1" in comparison_data or "files_only_in_group2" in comparison_data:
        raise PxygenError(
            "这是旧版 File_Compare 报告;pxygen 只支持 fcmp 的 JSON 报告"
            "(unique_in_a / unique_in_b),请用 fcmp 重新比对。"
        )

    file_list: list[str] = list(comparison_data.get(f"unique_in_{side}", []))

    # Also include files whose proxy exists but has a mismatched frame count
    if "frame_mismatches" in comparison_data:
        path_key = f"path_{side}"
        mismatch_files = [m[path_key] for m in comparison_data["frame_mismatches"]]
        file_list.extend(mismatch_files)
        output(f"已从 frame_mismatches 追加 {len(mismatch_files)} 个文件(side {side})")
        logger.info(
            "Added %d frame-mismatch file(s) for side %s",
            len(mismatch_files),
            side,
        )

    if not file_list:
        raise PxygenError(f"unique_in_{side} 中没有文件")

    if in_depth < 0 or out_depth < 0:
        raise ValueError("深度值 (-n/-d) 必须 ≥ 0")
    if out_depth < in_depth:
        raise ValueError("输出深度 (-d) 必须 ≥ 输入深度 (-n)")

    group_key = f"group_{side}"
    root_dirs: list[str] = [
        str(directory)
        for directory in (comparison_data.get(group_key) or {}).get("directories", [])
    ]
    if not root_dirs:
        raise PxygenError(
            f"报告中没有素材根目录({group_key}.directories 缺失或为空),"
            "请用 fcmp 重新比对。"
        )

    # Longest root first so a file under nested roots matches the deepest one.
    root_parts_list = sorted(
        (path_parts(directory) for directory in root_dirs), key=len, reverse=True
    )

    files_by_root: dict[tuple[str, ...], list[str]] = {}
    shallow_files: list[str] = []
    unmatched_files: list[str] = []
    for file_path in file_list:
        parts = path_parts(file_path)
        root_parts = next(
            (root for root in root_parts_list if parts[: len(root)] == root), None
        )
        if root_parts is None:
            unmatched_files.append(file_path)
            continue
        if len(parts) <= len(root_parts) + in_depth:
            shallow_files.append(file_path)
            continue
        files_by_root.setdefault(tuple(root_parts), []).append(file_path)

    logger.info("Found %d file(s) in unique_in_%s", len(file_list), side)
    summary_rows: list[tuple[str, object]] = [
        ("报告文件", json_path),
        ("比对侧", f"unique_in_{side}"),
        ("素材根目录", ", ".join(root_dirs)),
        ("深度", f"-n {in_depth} / -d {out_depth}"),
        ("文件数", len(file_list)),
    ]
    example_root = next(iter(files_by_root), None)
    if example_root is not None:
        example = files_by_root[example_root][0]
        parts = path_parts(example)
        key_end = len(example_root) + in_depth
        if in_depth == out_depth:
            summary_rows.extend(
                [
                    ("示例", example),
                    ("分组文件夹", parts[key_end - 1]),
                ]
            )
        else:
            fragment_parts = parts[key_end - 1:len(example_root) + out_depth]
            summary_rows.extend(
                [
                    ("示例", example),
                    (
                        "分组片段",
                        format_path_parts(
                            fragment_parts,
                            windows=":" in example[:3] or "\\" in example,
                        ),
                    ),
                ]
            )
    output_kv("JSON 模式", summary_rows, output)

    skipped_groups = [
        (f"不在 {group_key} 目录之下", unmatched_files),
        (
            f"距素材根目录不足 {in_depth} 层,无法按 -n {in_depth} 分组",
            shallow_files,
        ),
    ]
    for reason, skipped in skipped_groups:
        if not skipped:
            continue
        output(f"\n警告:跳过 {len(skipped)} 个文件({reason}):")
        for file_path in skipped:
            output(f"  {file_path}")
        # info, not warning — the output() lines above already surface this
        # to the user; warning level would print it twice on the console.
        logger.info("Skipped %d file(s) (%s): %s", len(skipped), reason, skipped)

    # Keys from different roots can never collide (they embed the root path),
    # so a plain merge is safe.
    organized: dict[str, dict[str, list[str]]] = {}
    for root_parts_key, files in files_by_root.items():
        organized.update(
            organize_json_mode_files(
                files,
                len(root_parts_key) + in_depth,
                len(root_parts_key) + out_depth,
            )
        )
    if not organized:
        raise PxygenError("没有文件能归入素材根目录之下的分组。")
    logger.debug("JSON mode produced %d top-level folder group(s)", len(organized))
    if filter_mode == "select":
        options = describe_folders_at_in_depth(organized)
        selected_indices = _read_selection_indices(
            options, input_func=input_func, output=output
        )
        if selected_indices is not None:
            logger.debug("JSON mode selected folder indices: %s", selected_indices)
            organized = select_folders_at_in_depth(organized, selected_indices)
    elif filter_mode == "filter" and filter_list:
        organized_before_filter = organized
        organized = filter_folders_at_in_depth(organized, filter_list)
        if not organized:
            available = ", ".join(sorted(path_name(k) for k in organized_before_filter))
            output(f"\n警告:筛选无匹配文件夹:{' '.join(filter_list)}")
            output(f"可选文件夹:{available}")
            logger.warning(
                "No matching folders found for filter %r (available: %s)",
                filter_list,
                available,
            )
        else:
            logger.debug("JSON mode filter %r kept %d folder group(s)", filter_list, len(organized))

    if not organized:
        raise PxygenError("筛选后没有可处理的文件夹。")

    plan = build_resolve_execution_plan(
        organized,
        list(organized),
        proxy_path,
        mode_name="json",
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
    filter_mode: str | None = None,
    filter_list: list[str] | None = None,
    codec: str = "auto",
    input_func: InputFn | None = None,
    output: OutputFn | None = None,
    confirm_render: Callable[[], bool] | None = None,
) -> None:
    """Import footage directly from a folder hierarchy and generate proxies.

    Args:
        footage_path: Root footage directory.
        proxy_path: Root output directory for proxies.
        in_depth: Folder level relative to the provided footage root.
        out_depth: Batch level relative to the provided footage root.
        filter_mode: ``'select'`` or ``'filter'`` or ``None``.
        filter_list: Folder names to keep (only used when
            filter_mode == ``'filter'``).
        codec: Render codec selection.
    """
    output = output or print
    input_func = input_func or input
    logger.info(
        "Running directory mode footage_path=%s proxy_path=%s in_depth=%d out_depth=%d",
        footage_path,
        proxy_path,
        in_depth,
        out_depth,
    )

    footage_dir = Path(footage_path)
    if not footage_dir.exists():
        raise PxygenError(f"素材文件夹不存在:{footage_path}")
    footage_depth = len(path_parts(footage_path))
    in_depth_spec = _normalize_depth(footage_depth, in_depth)
    out_depth_spec = _normalize_depth(footage_depth, out_depth)
    if out_depth_spec.resolved < in_depth_spec.resolved:
        raise ValueError("输出深度 (-d) 必须 ≥ 输入深度 (-n)")
    # --- Walk to find all folders at exactly in_depth ---
    input_depth_folders = [
        str(path) for path in _collect_directories_at_depth(footage_dir, in_depth_spec.resolved)
    ]
    logger.debug(
        "Directory mode discovered %d folder(s) at input depth %d",
        len(input_depth_folders),
        in_depth_spec.resolved,
    )
    logger.info(
        "Discovered %d folder(s) at input depth %d for %s",
        len(input_depth_folders),
        in_depth_spec.resolved,
        footage_path,
    )

    if not input_depth_folders:
        raise PxygenError(
            f"'{footage_path}' 之下深度 {in_depth} 处没有文件夹"
        )

    output_kv(
        "目录模式",
        [
            ("素材", f"{footage_path}(深度 {footage_depth})"),
            ("代理", proxy_path),
            ("深度", f"-n {in_depth_spec.requested} / -d {out_depth_spec.requested}"),
            ("文件夹数", len(input_depth_folders)),
        ],
        output,
    )

    # --- For each input folder, collect target folders at out_depth ---
    # If a branch is shallower than out_depth, use the deepest available level.
    targets_by_input: dict[str, list[str]] = {}

    for input_folder in input_depth_folders:
        if in_depth_spec.resolved == out_depth_spec.resolved:
            targets_by_input[input_folder] = [input_folder]
            continue

        target_folders: list[str] = []
        max_depth_found = in_depth_spec.resolved
        directory_tree = _collect_directory_tree(Path(input_folder))

        for root in directory_tree:
            current_depth = len(path_parts(root))
            max_depth_found = max(max_depth_found, current_depth)
            if current_depth == out_depth_spec.resolved:
                target_folders.append(str(root))

        if not target_folders and max_depth_found < out_depth_spec.resolved:
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
        output_numbered(
            f"文件夹({len(folder_paths)} 个):", _folder_labels(folder_paths), output
        )
        output(_SELECTION_HINT)
        choice = prompt_line(input_func)
        if choice.lower() == "all":
            selected_indices = None
        else:
            selected_indices = parse_selection(choice, len(folder_paths))
        if selected_indices is not None:
            selected = [folder_paths[i] for i in selected_indices]
            logger.debug("Directory mode selected folder paths: %s", selected)
            targets_by_input = {p: targets_by_input[p] for p in selected}

    elif filter_mode == "filter" and filter_list:
        filter_names = set(normalize_filter_names(filter_list))
        filtered = {
            fp: targets
            for fp, targets in targets_by_input.items()
            if path_name(fp) in filter_names
        }
        if not filtered:
            available = sorted(path_name(fp) for fp in targets_by_input)
            logger.warning(
                "No matching folders found for filter %r (available: %s)",
                filter_list,
                ", ".join(available),
            )
            raise PxygenError(
                f"筛选无匹配文件夹:{' '.join(filter_names)}"
                f"(可选:{', '.join(available)})"
            )
        targets_by_input = filtered
        logger.debug("Directory mode filter %r kept %d input folder(s)", filter_list, len(filtered))

    if not targets_by_input:
        raise PxygenError("筛选后没有可处理的文件夹。")

    all_target_folders: list[str] = [
        folder for targets in targets_by_input.values() for folder in targets
    ]
    output(f"\n共处理 {len(all_target_folders)} 个文件夹")
    logger.info("Total folders to process: %d", len(all_target_folders))

    if in_depth_spec.resolved == out_depth_spec.resolved:
        organized = organize_directory_mode_folders(all_target_folders, in_depth_spec.resolved)
    else:
        organized = organize_json_mode_files(
            all_target_folders,
            in_depth_spec.resolved,
            out_depth_spec.resolved,
        )

    if not organized:
        organized = {footage_path: {"": all_target_folders}}

    plan = build_resolve_execution_plan(
        organized,
        list(organized),
        proxy_path,
        mode_name="directory",
        codec=codec,
    )
    logger.debug(
        "Built directory mode execution plan with %d footage folder(s)",
        len(plan.footage_folders),
    )
    execute_resolve_plan(plan, output=output, confirm_render=confirm_render)
