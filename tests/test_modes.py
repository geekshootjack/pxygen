"""Tests for pxygen.modes orchestration."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pxygen.modes import list_footage_folders, process_directory_mode, process_json_mode
from pxygen.plan import ResolveExecutionPlan
from pxygen.resolve import ProxyGeneratorError


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
                clean_image=True,
            )

        plan = mock_execute.call_args.args[0]
        assert isinstance(plan, ResolveExecutionPlan)
        assert plan.proxy_folder_path == "/proxy"
        assert {folder.footage_folder_path for folder in plan.footage_folders} == {
            "/Volumes/SSD/Footage/Day2"
        }
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
        assert plan.clean_image is True
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
                filter_list="Day2",
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [
            "/Volumes/SSD/Footage/Day2"
        ]

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

        with pytest.raises(ProxyGeneratorError, match="No folders to process after filtering"):
            process_json_mode(
                str(json_path),
                "/proxy",
                1,
                1,
                2,
                filter_mode="filter",
                filter_list="Day99",
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
        assert "JSON mode:" in output_text
        assert "Parameter" in output_text
        assert "Value" in output_text
        assert "Dataset" in output_text
        assert "File count" in output_text
        assert "━" in output_text

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
    def test_list_footage_folders_accepts_relative_levels(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "Day2").mkdir(parents=True)

        assert list_footage_folders(str(footage_root), 1) == [
            str(footage_root / "Day1"),
            str(footage_root / "Day2"),
        ]

    def test_list_footage_folders_no_longer_treats_depth_as_absolute(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)

        assert list_footage_folders(str(footage_root), 4) == []

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
                filter_list="Day1",
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [str(day1)]
        assert plan.footage_folders[0].batches[0].subfolder_key == ""
        assert list(plan.footage_folders[0].batches[0].items) == [str(day1)]
        assert plan.project_prefix == "proxy"

    def test_falls_back_to_deepest_available_level_when_branch_is_shallow(self, tmp_path):
        footage_root = tmp_path / "footage"
        shallow_leaf = footage_root / "Day1" / "CamA"
        shallow_leaf.mkdir(parents=True)
        day1 = footage_root / "Day1"

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(str(footage_root), "/proxy", 1, 3)

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [str(day1)]
        assert plan.footage_folders[0].batches[0].subfolder_key == "CamA"
        assert list(plan.footage_folders[0].batches[0].items) == [str(shallow_leaf)]

    def test_select_mode_keeps_only_chosen_input_folders(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1" / "CamA").mkdir(parents=True)
        (footage_root / "Day2" / "CamA").mkdir(parents=True)
        day2 = footage_root / "Day2"

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
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [str(day2)]

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

    def test_outputs_directory_summary_and_selection_as_tables(self, tmp_path):
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
        assert "Directory mode:" in output_text
        assert "Parameter" in output_text
        assert "Value" in output_text
        assert "Folders at depth" in output_text
        assert "#" in output_text
        assert "Folder" in output_text
        assert "Sub-folders" not in output_text
        assert "━" in output_text

    def test_gsdata_folders_are_excluded_from_traversal(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "_gsdata_").mkdir(parents=True)

        result = list_footage_folders(str(footage_root), 1)

        assert result == [str(footage_root / "Day1")]
