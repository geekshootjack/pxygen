"""Tests for terminal structure previews."""
from __future__ import annotations

from pxygen.plan import PlannedBatch, PlannedFootageFolder, ResolveExecutionPlan
from pxygen.presenter import ConsolePresenter
from pxygen.preview import show_structure_preview


def test_show_structure_preview_renders_input_and_output_trees():
    plan = ResolveExecutionPlan(
        mode_name="directory",
        project_prefix="proxy",
        proxy_folder_path="H:\\proxy",
        clean_image=False,
        codec="auto",
        footage_folders=(
            PlannedFootageFolder(
                footage_folder_path="K:\\素材\\260102-北京站",
                footage_folder_name="260102-北京站",
                batches=(
                    PlannedBatch(
                        subfolder_key="多机位/FX3#1",
                        items=("K:\\素材\\260102-北京站\\多机位\\FX3#1",),
                        bin_parts=("多机位", "FX3#1"),
                        target_dir="H:\\proxy\\260102-北京站\\多机位\\FX3#1",
                    ),
                    PlannedBatch(
                        subfolder_key="多机位/FX3#2",
                        items=("K:\\素材\\260102-北京站\\多机位\\FX3#2",),
                        bin_parts=("多机位", "FX3#2"),
                        target_dir="H:\\proxy\\260102-北京站\\多机位\\FX3#2",
                    ),
                ),
            ),
        ),
    )
    output_lines: list[str] = []
    presenter = ConsolePresenter(output_func=output_lines.append, input_func=lambda: "")

    show_structure_preview(
        plan,
        input_root="K:\\素材",
        proxy_root="H:\\proxy",
        presenter=presenter,
    )

    output_text = "\n".join(output_lines)
    assert "Input" in output_text
    assert "Output" in output_text
    assert "260102-北京站" in output_text
    assert "多机位" in output_text
    assert "FX3#1" in output_text
    assert "H:\\proxy" in output_text
