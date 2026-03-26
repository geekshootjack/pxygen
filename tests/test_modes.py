"""Tests for pxygen.modes orchestration."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pxygen.modes import process_directory_mode, process_json_mode
from pxygen.paths import path_parts
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
                4,
                5,
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
                4,
                5,
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
                4,
                5,
                filter_mode="filter",
                filter_list="Day99",
            )


class TestProcessDirectoryMode:
    def test_in_depth_equals_out_depth_groups_input_folders(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1").mkdir(parents=True)
        (footage_root / "Day2").mkdir(parents=True)
        day1 = footage_root / "Day1"
        in_depth = len(path_parts(day1))

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(
                str(footage_root),
                "/proxy",
                in_depth,
                in_depth,
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
        in_depth = len(path_parts(day1))
        out_depth = in_depth + 2

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute:
            process_directory_mode(str(footage_root), "/proxy", in_depth, out_depth)

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [str(day1)]
        assert plan.footage_folders[0].batches[0].subfolder_key == "CamA"
        assert list(plan.footage_folders[0].batches[0].items) == [str(shallow_leaf)]

    def test_select_mode_keeps_only_chosen_input_folders(self, tmp_path):
        footage_root = tmp_path / "footage"
        (footage_root / "Day1" / "CamA").mkdir(parents=True)
        (footage_root / "Day2" / "CamA").mkdir(parents=True)
        day1 = footage_root / "Day1"
        day2 = footage_root / "Day2"
        in_depth = len(path_parts(day1))
        out_depth = in_depth + 1

        with patch("pxygen.modes.execute_resolve_plan") as mock_execute, patch(
            "builtins.input", return_value="2"
        ):
            process_directory_mode(
                str(footage_root),
                "/proxy",
                in_depth,
                out_depth,
                filter_mode="select",
            )

        plan = mock_execute.call_args.args[0]
        assert [folder.footage_folder_path for folder in plan.footage_folders] == [str(day2)]
