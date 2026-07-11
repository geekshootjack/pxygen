"""Tests for pxygen.modes orchestration."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pxygen.modes import (
    _collect_directories_at_depth,
    process_directory_mode,
    process_json_mode,
)
from pxygen.paths import path_parts
from pxygen.plan import ResolveExecutionPlan
from pxygen.resolve import PxygenError


class TestProcessJsonMode:
    def test_merges_selected_dataset_and_frame_mismatches(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group2": [
                        "/Volumes/SSD/Footage/Day2/CamA/clip1.mov",
                    ],
                    "frame_count_mismatches": [
                        {
                            "path1": "/unused/group1.mov",
                            "path2": "/Volumes/SSD/Footage/Day2/CamB/clip2.mov",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_json_mode(
                str(json_path),
                "/proxy",
                2,
                1,
                2,
                codec="prores",
            )

        plan = mock_execute.call_args.args[0]
        assert isinstance(plan, ResolveExecutionPlan)
        assert {folder.footage_folder_name for folder in plan.footage_folders} == {"Day2"}
        batches = {
            batch.subfolder_key: list(batch.items) for batch in plan.footage_folders[0].batches
        }
        assert batches["CamA"] == [
            "/Volumes/SSD/Footage/Day2/CamA/clip1.mov"
        ]
        assert batches["CamB"] == [
            "/Volumes/SSD/Footage/Day2/CamB/clip2.mov"
        ]
        assert plan.codec == "prores"
        assert plan.project_prefix == "proxy_redo"

    def test_filter_mode_limits_selected_folders(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                        "/Volumes/SSD/Footage/Day2/CamA/clip2.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
                filter_mode="filter",
                filter_list=["Day2"],
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day2"]

    def test_raises_when_filter_removes_everything(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(PxygenError, match="No folders to process after filtering"):
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
                filter_mode="filter",
                filter_list=["Day99"],
            )

    def test_outputs_json_summary_as_table(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )
        output_lines: list[str] = []

        with patch("pxygen.modes.execute_resolve_plan"):
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
                output=output_lines.append,
            )

        output_text = "\n".join(output_lines)
        assert "JSON mode" in output_text
        assert "dataset" in output_text
        assert "group1" in output_text
        assert "files" in output_text

    def test_defaults_to_console_output_instead_of_logger_info(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )

        with (
            patch("pxygen.modes.execute_resolve_plan"),
            patch("builtins.print") as mock_print,
        ):
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
            )

        assert mock_print.called

    def test_single_parent_json_still_groups_by_parent_folder(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                        "/Volumes/SSD/Footage/Day1/CamA/clip2.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                1,
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["CamA"]

    def test_relative_depths_group_json_paths_from_common_root(self, tmp_path):
        json_path = tmp_path / "comparison.json"
        json_path.write_text(
            json.dumps(
                {
                    "files_only_in_group1": [
                        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
                        "/Volumes/SSD/Footage/Day1/CamB/clip2.mov",
                        "/Volumes/SSD/Footage/Day2/CamA/clip3.mov",
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day1", "Day2"]
        day1_batches = {
            batch.subfolder_key: list(batch.items)
            for batch in plan.footage_folders[0].batches
        }
        assert sorted(day1_batches) == ["CamA", "CamB"]
        assert day1_batches["CamA"] == ["/Volumes/SSD/Footage/Day1/CamA/clip1.mov"]


class TestProcessDirectoryMode:
    def test_traversal_depth_is_relative_to_input_root(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "Day2").mkdir(parents=True)
        root_depth = len(path_parts(str(footage_root)))

        assert _collect_directories_at_depth(footage_root, root_depth + 1) == [
            footage_root / "Day1",
            footage_root / "Day2",
        ]

    def test_traversal_finds_nothing_past_the_deepest_level(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        root_depth = len(path_parts(str(footage_root)))

        assert _collect_directories_at_depth(footage_root, root_depth + 4) == []

    def test_in_depth_equals_out_depth_groups_input_folders(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "Day2").mkdir(parents=True)
        day1 = footage_root / "Day1"

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(
                str(footage_root),
                "/proxy",
                1,
                1,
                filter_mode="filter",
                filter_list=["Day1"],
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day1"]
        assert plan.footage_folders[0].batches[0].subfolder_key == ""
        assert list(plan.footage_folders[0].batches[0].items) == [str(day1)]
        assert plan.project_prefix == "proxy"

    def test_falls_back_to_deepest_available_level_when_branch_is_shallow(self, tmp_path):
        footage_root = tmp_path / "footage"
        shallow_leaf = footage_root / "Day1" / "CamA"
        shallow_leaf.mkdir(parents=True)
        footage_root / "Day1"

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(str(footage_root), "/proxy", 1, 3)

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day1"]
        assert plan.footage_folders[0].batches[0].subfolder_key == "CamA"
        assert list(plan.footage_folders[0].batches[0].items) == [str(shallow_leaf)]

    def test_select_mode_keeps_only_chosen_input_folders(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1" / "CamA").mkdir(parents=True)
        (footage_root / "Day2" / "CamA").mkdir(parents=True)
        footage_root / "Day2"

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute, patch(
            "builtins.input", return_value="2"
        ):
            process_directory_mode(
                str(footage_root),
                "/proxy",
                1,
                2,
                filter_mode="select",
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day2"]

    def test_relative_depths_group_directory_tree_from_input_root(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1" / "CamA").mkdir(parents=True)
        (footage_root / "Day1" / "CamB").mkdir(parents=True)
        (footage_root / "Day2" / "CamA").mkdir(parents=True)

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(
                str(footage_root),
                "/proxy",
                1,
                2,
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_name for folder in plan.footage_folders] == ["Day1", "Day2"]
        day1_batches = {
            batch.subfolder_key: list(batch.items)
            for batch in plan.footage_folders[0].batches
        }
        assert sorted(day1_batches) == ["CamA", "CamB"]
        assert day1_batches["CamA"] == [str(footage_root / "Day1" / "CamA")]

    def test_outputs_directory_summary_and_selection_as_compact_blocks(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1" / "CamA").mkdir(parents=True)
        (footage_root / "Day2" / "CamA").mkdir(parents=True)
        output_lines: list[str] = []

        with (
            patch("pxygen.modes.execute_resolve_plan"),
            patch("builtins.input", return_value="all"),
        ):
            process_directory_mode(
                str(footage_root),
                "/proxy",
                1,
                2,
                filter_mode="select",
                output=output_lines.append,
            )

        output_text = "\n".join(output_lines)
        assert "Directory mode" in output_text
        assert "footage" in output_text
        assert "proxy" in output_text
        assert "Folders (2):" in output_text
        # leaf names only — the common path prefix is not repeated per row
        assert "  1  Day1" in output_text
        assert "  2  Day2" in output_text
        assert "━" not in output_text

    def test_gsdata_folders_are_excluded_from_traversal(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "_gsdata_").mkdir(parents=True)
        root_depth = len(path_parts(str(footage_root)))

        result = _collect_directories_at_depth(footage_root, root_depth + 1)

        assert result == [footage_root / "Day1"]
