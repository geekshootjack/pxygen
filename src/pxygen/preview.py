"""Terminal previews for depth/grouping behavior."""
from __future__ import annotations

from pathlib import Path

from rich.columns import Columns
from rich.panel import Panel
from rich.tree import Tree

from .paths import path_parts
from .plan import ResolveExecutionPlan
from .presenter import ConsolePresenter


def _display_root_label(path: str) -> str:
    cleaned = path.rstrip("/\\")
    if not cleaned:
        return path
    return Path(cleaned).name or cleaned


def _relative_parts(root_path: str, target_path: str) -> tuple[str, ...]:
    root_parts = path_parts(root_path)
    target_parts = path_parts(target_path)
    if len(target_parts) >= len(root_parts) and target_parts[: len(root_parts)] == root_parts:
        return tuple(target_parts[len(root_parts):])
    return tuple(target_parts)


def _insert_tree_path(root: Tree, parts: tuple[str, ...]) -> None:
    current = root
    for part in parts:
        existing = next(
            (child for child in current.children if getattr(child, "label", None) == part),
            None,
        )
        if existing is None:
            existing = current.add(part)
        current = existing


def _build_input_tree(
    plan: ResolveExecutionPlan,
    input_root: str,
    root_label: str | None = None,
) -> Tree:
    tree = Tree(root_label or _display_root_label(input_root))
    for footage_folder in plan.footage_folders:
        for batch in footage_folder.batches:
            path_parts_tuple = (
                _relative_parts(input_root, footage_folder.footage_folder_path)
                + batch.bin_parts
            )
            if not path_parts_tuple:
                path_parts_tuple = (footage_folder.footage_folder_name,)
            _insert_tree_path(tree, path_parts_tuple)
    return tree


def _build_output_tree(plan: ResolveExecutionPlan, proxy_root: str) -> Tree:
    tree = Tree(proxy_root)
    for footage_folder in plan.footage_folders:
        for batch in footage_folder.batches:
            path_parts_tuple = _relative_parts(proxy_root, batch.target_dir)
            if not path_parts_tuple:
                path_parts_tuple = (footage_folder.footage_folder_name,)
            _insert_tree_path(tree, path_parts_tuple)
    return tree


def show_structure_preview(
    plan: ResolveExecutionPlan,
    *,
    input_root: str,
    proxy_root: str,
    presenter: ConsolePresenter,
    input_root_label: str | None = None,
) -> None:
    """Render a terminal preview of input and output trees."""
    input_tree = _build_input_tree(plan, input_root, input_root_label)
    output_tree = _build_output_tree(plan, proxy_root)
    presenter.show("")
    presenter.show_renderable(
        Columns(
            [
                Panel(input_tree, title="Input", border_style="green"),
                Panel(output_tree, title="Output", border_style="cyan"),
            ],
            expand=True,
            equal=True,
        )
    )
