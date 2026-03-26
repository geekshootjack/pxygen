"""Internal execution-plan models shared by modes and Resolve execution."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import split_subfolder_key


@dataclass(frozen=True)
class PlannedBatch:
    """A single import/render batch under one footage folder."""

    subfolder_key: str
    items: tuple[str, ...]
    bin_parts: tuple[str, ...]
    target_dir: str


@dataclass(frozen=True)
class PlannedFootageFolder:
    """All batches associated with one top-level footage folder."""

    footage_folder_path: str
    footage_folder_name: str
    batches: tuple[PlannedBatch, ...]


@dataclass(frozen=True)
class ResolveExecutionPlan:
    """Serializable-ish description of what Resolve should do."""

    mode_name: str
    project_prefix: str
    proxy_folder_path: str
    clean_image: bool
    codec: str
    footage_folders: tuple[PlannedFootageFolder, ...]


def build_resolve_execution_plan(
    organized_files: dict[str, dict[str, list[str]]],
    selected_footage_folders: list[str],
    proxy_folder_path: str,
    *,
    mode_name: str,
    clean_image: bool = False,
    codec: str = "auto",
) -> ResolveExecutionPlan:
    """Build an execution plan from organized folder mappings."""
    project_prefix = "proxy" if mode_name == "directory" else "proxy_redo"
    footage_folders: list[PlannedFootageFolder] = []

    for footage_folder_path in selected_footage_folders:
        footage_folder_name = Path(footage_folder_path).name
        batches: list[PlannedBatch] = []

        for subfolder_key, items in sorted(organized_files[footage_folder_path].items()):
            bin_parts = split_subfolder_key(subfolder_key)
            proxy_target = Path(proxy_folder_path) / footage_folder_name
            if bin_parts:
                proxy_target = proxy_target.joinpath(*bin_parts)
            batches.append(
                PlannedBatch(
                    subfolder_key=subfolder_key,
                    items=tuple(items),
                    bin_parts=bin_parts,
                    target_dir=str(proxy_target),
                )
            )

        footage_folders.append(
            PlannedFootageFolder(
                footage_folder_path=footage_folder_path,
                footage_folder_name=footage_folder_name,
                batches=tuple(batches),
            )
        )

    return ResolveExecutionPlan(
        mode_name=mode_name,
        project_prefix=project_prefix,
        proxy_folder_path=proxy_folder_path,
        clean_image=clean_image,
        codec=codec,
        footage_folders=tuple(footage_folders),
    )
