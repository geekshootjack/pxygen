"""
Unit tests for pure Python logic in Proxy_generator.py.

These tests require NO DaVinci Resolve instance — the Resolve API is mocked in
conftest.py before this module is imported.

Functions NOT yet testable here (tightly coupled to Resolve API):
  - process_files_in_resolve()   → needs Resolve mock + significant restructuring
  - calculate_proxy_dimensions() → nested inside process_files_in_resolve;
                                   extract it during refactor, then add tests here
  - process_json_mode()          → calls process_files_in_resolve at the end
  - process_directory_mode()     → calls process_files_in_resolve at the end

The interactive select path of filter_folders_at_in_depth() uses input() which
is tested here via unittest.mock.patch.

Note: path tests use Unix-style absolute paths (macOS/Linux). The underlying logic
uses os.sep and os.path.join, so tests are portable across platforms when run with
paths that match the host OS separator.
"""

import os
import pytest
from unittest.mock import patch

import Proxy_generator as pg


# ---------------------------------------------------------------------------
# clean_path_input
# ---------------------------------------------------------------------------

class TestCleanPathInput:
    def test_removes_shell_escaped_space(self):
        assert pg.clean_path_input("/path\\ with\\ spaces/file") == "/path with spaces/file"

    def test_removes_shell_escaped_hash(self):
        assert pg.clean_path_input("/path\\#footage") == "/path#footage"

    def test_strips_surrounding_double_quotes(self):
        assert pg.clean_path_input('"/Volumes/SSD/Footage"') == "/Volumes/SSD/Footage"

    def test_strips_surrounding_whitespace(self):
        assert pg.clean_path_input("  /Volumes/SSD/Footage  ") == "/Volumes/SSD/Footage"

    def test_strips_quotes_and_whitespace_combined(self):
        assert pg.clean_path_input('"  /Volumes/SSD/Footage  "') == "/Volumes/SSD/Footage"

    def test_normalizes_lowercase_windows_drive_letter(self):
        assert pg.clean_path_input("c:/Users/footage") == "C:/Users/footage"

    def test_normalizes_lowercase_d_drive(self):
        assert pg.clean_path_input("d:\\footage\\day1") == "D:\\footage\\day1"

    def test_leaves_uppercase_windows_drive_unchanged(self):
        assert pg.clean_path_input("C:/Users/footage") == "C:/Users/footage"

    def test_unix_path_unchanged(self):
        assert pg.clean_path_input("/Volumes/SSD/Footage") == "/Volumes/SSD/Footage"

    def test_shell_escape_and_quotes_combined(self):
        assert pg.clean_path_input('"/path\\ with space"') == "/path with space"

    def test_non_windows_two_char_path_not_uppercased(self):
        # Only uppercase if path[1] == ':'. A path like "/a/b" should not be touched.
        assert pg.clean_path_input("/a/footage") == "/a/footage"


# ---------------------------------------------------------------------------
# compute_key_path
# ---------------------------------------------------------------------------

class TestComputeKeyPath:
    def test_basic_depth_returns_correct_path(self):
        parts = ["Volumes", "SSD", "Footage", "Day1", "CamA"]
        result = pg.compute_key_path(parts, 3, leading_sep=False)
        assert result == os.path.join("Volumes", "SSD", "Footage")

    def test_zero_depth_raises_value_error(self):
        with pytest.raises(ValueError):
            pg.compute_key_path(["a", "b"], 0)

    def test_negative_depth_raises_value_error(self):
        with pytest.raises(ValueError):
            pg.compute_key_path(["a", "b"], -1)

    def test_parts_shorter_than_depth_returns_none(self):
        parts = ["Volumes", "SSD"]
        assert pg.compute_key_path(parts, 5) is None

    def test_depth_equals_parts_length(self):
        parts = ["a", "b", "c"]
        result = pg.compute_key_path(parts, 3, leading_sep=False)
        assert result == os.path.join("a", "b", "c")

    def test_depth_one_returns_single_component(self):
        parts = ["Volumes", "SSD", "Footage"]
        result = pg.compute_key_path(parts, 1, leading_sep=False)
        assert result == "Volumes"

    def test_leading_sep_true_adds_separator_prefix(self):
        parts = ["Volumes", "SSD", "Footage", "Day1"]
        result = pg.compute_key_path(parts, 4, leading_sep=True)
        assert result.startswith(os.sep)

    def test_leading_sep_false_no_separator_prefix(self):
        parts = ["Volumes", "SSD", "Footage"]
        result = pg.compute_key_path(parts, 2, leading_sep=False)
        assert not result.startswith(os.sep)

    def test_leading_sep_not_added_twice_if_already_present(self):
        # If the result already starts with os.sep, it must not be doubled.
        parts = ["Volumes", "SSD"]
        result = pg.compute_key_path(parts, 1, leading_sep=True)
        assert not result.startswith(os.sep + os.sep)


# ---------------------------------------------------------------------------
# parse_selection
# ---------------------------------------------------------------------------

class TestParseSelection:
    def test_single_number(self):
        assert pg.parse_selection("1", 5) == [0]

    def test_single_number_last_item(self):
        assert pg.parse_selection("5", 5) == [4]

    def test_range(self):
        assert pg.parse_selection("2-4", 5) == [1, 2, 3]

    def test_range_full_span(self):
        assert pg.parse_selection("1-3", 3) == [0, 1, 2]

    def test_comma_separated(self):
        assert pg.parse_selection("1,3,5", 5) == [0, 2, 4]

    def test_mixed_range_and_single(self):
        assert pg.parse_selection("1,3,5-7", 10) == [0, 2, 4, 5, 6]

    def test_duplicates_are_removed(self):
        assert pg.parse_selection("1,1,2", 5) == [0, 1]

    def test_result_is_sorted(self):
        assert pg.parse_selection("3,1,2", 5) == [0, 1, 2]

    def test_number_exceeding_max_is_ignored(self):
        assert pg.parse_selection("6", 5) == []

    def test_zero_is_ignored(self):
        # "0" → idx = -1, which fails the 0 <= idx check
        assert pg.parse_selection("0", 5) == []

    def test_invalid_string_is_ignored(self):
        assert pg.parse_selection("abc", 5) == []

    def test_empty_string_returns_empty(self):
        assert pg.parse_selection("", 5) == []

    def test_whitespace_around_numbers_is_handled(self):
        assert pg.parse_selection(" 1 , 2 ", 5) == [0, 1]

    def test_malformed_range_is_ignored(self):
        # "1-" splits to ["1", ""] → int("") raises ValueError → skipped
        assert pg.parse_selection("1-", 5) == []


# ---------------------------------------------------------------------------
# organize_json_mode_files
# ---------------------------------------------------------------------------

class TestOrganizeJsonModeFiles:
    """
    Test file structure (Unix paths):

        /Volumes/SSD/Footage/Day1/CamA/clip1.mov   depth-5 group: CamA
        /Volumes/SSD/Footage/Day1/CamA/clip2.mov   depth-5 group: CamA
        /Volumes/SSD/Footage/Day1/CamB/clip3.mov   depth-5 group: CamB
        /Volumes/SSD/Footage/Day2/CamA/clip4.mov   depth-5 group: CamA (Day2)

    Absolute depths on macOS (/=0, Volumes=1, SSD=2, Footage=3, Day=4, Cam=5, clip=6)
    """

    FILES = [
        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
        "/Volumes/SSD/Footage/Day1/CamA/clip2.mov",
        "/Volumes/SSD/Footage/Day1/CamB/clip3.mov",
        "/Volumes/SSD/Footage/Day2/CamA/clip4.mov",
    ]

    def test_groups_by_camera_level_in_depth_5(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=5, out_depth=5)
        # 3 camera-level groups: Day1/CamA, Day1/CamB, Day2/CamA
        assert len(result) == 3

    def test_groups_by_day_level_in_depth_4(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        # 2 day-level groups: Day1, Day2
        assert len(result) == 2

    def test_subfolder_key_is_empty_when_depths_equal(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        for key_path in result:
            assert "" in result[key_path]

    def test_subfolder_key_populated_when_out_depth_greater(self):
        # in_depth=4 (Day), out_depth=5 (Cam): subfolders are CamA / CamB
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=5)
        day1_key = next(k for k in result if "Day1" in k)
        subfolders = result[day1_key]
        assert "CamA" in subfolders
        assert "CamB" in subfolders

    def test_correct_files_assigned_to_day1_group(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        day1_key = next(k for k in result if "Day1" in k)
        files = result[day1_key][""]
        assert "/Volumes/SSD/Footage/Day1/CamA/clip1.mov" in files
        assert "/Volumes/SSD/Footage/Day1/CamA/clip2.mov" in files
        assert "/Volumes/SSD/Footage/Day1/CamB/clip3.mov" in files
        # Day2 file must NOT appear in Day1 group
        assert "/Volumes/SSD/Footage/Day2/CamA/clip4.mov" not in files

    def test_correct_files_assigned_to_day2_group(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        day2_key = next(k for k in result if "Day2" in k)
        files = result[day2_key][""]
        assert "/Volumes/SSD/Footage/Day2/CamA/clip4.mov" in files
        assert len(files) == 1

    def test_files_shallower_than_in_depth_are_skipped(self):
        short_paths = ["/a/b.mov"]  # only 2 components
        result = pg.organize_json_mode_files(short_paths, in_depth=5, out_depth=5)
        assert result == {}

    def test_empty_file_list_returns_empty(self):
        result = pg.organize_json_mode_files([], in_depth=4, out_depth=4)
        assert result == {}

    def test_multiple_files_in_same_subfolder_grouped_together(self):
        result = pg.organize_json_mode_files(self.FILES, in_depth=4, out_depth=5)
        day1_key = next(k for k in result if "Day1" in k)
        cam_a_files = result[day1_key]["CamA"]
        assert len(cam_a_files) == 2
        assert "/Volumes/SSD/Footage/Day1/CamA/clip1.mov" in cam_a_files
        assert "/Volumes/SSD/Footage/Day1/CamA/clip2.mov" in cam_a_files


# ---------------------------------------------------------------------------
# organize_directory_mode_folders
# ---------------------------------------------------------------------------

class TestOrganizeDirectoryModeFolders:
    FOLDERS = [
        "/Volumes/SSD/Footage/Day1",
        "/Volumes/SSD/Footage/Day2",
        "/Volumes/SSD/Footage/Day3",
    ]

    def test_each_folder_becomes_its_own_key(self):
        result = pg.organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        assert len(result) == 3

    def test_subfolder_key_is_always_empty_string(self):
        result = pg.organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        for key_path in result:
            assert list(result[key_path].keys()) == [""]

    def test_folder_path_stored_as_single_item_list(self):
        result = pg.organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        day1_key = next(k for k in result if "Day1" in k)
        assert result[day1_key][""] == ["/Volumes/SSD/Footage/Day1"]

    def test_folders_shallower_than_in_depth_are_skipped(self):
        shallow = ["/a/b"]  # only 2 components
        result = pg.organize_directory_mode_folders(shallow, in_depth=5)
        assert result == {}

    def test_empty_folder_list_returns_empty(self):
        result = pg.organize_directory_mode_folders([], in_depth=4)
        assert result == {}


# ---------------------------------------------------------------------------
# filter_folders_at_in_depth
# ---------------------------------------------------------------------------

class TestFilterFoldersAtInDepth:
    ORGANIZED = {
        "/Volumes/SSD/Footage/Day1": {"": ["/Volumes/SSD/Footage/Day1"]},
        "/Volumes/SSD/Footage/Day2": {"": ["/Volumes/SSD/Footage/Day2"]},
        "/Volumes/SSD/Footage/Day3": {"": ["/Volumes/SSD/Footage/Day3"]},
    }

    def test_no_filter_mode_returns_input_unchanged(self):
        result = pg.filter_folders_at_in_depth(self.ORGANIZED, 4, filter_mode=None)
        assert result == self.ORGANIZED

    def test_filter_mode_keeps_matching_folders(self):
        result = pg.filter_folders_at_in_depth(
            self.ORGANIZED, 4, filter_mode="filter", filter_list="Day1,Day3"
        )
        assert len(result) == 2
        assert any("Day1" in k for k in result)
        assert any("Day3" in k for k in result)

    def test_filter_mode_excludes_non_matching_folders(self):
        result = pg.filter_folders_at_in_depth(
            self.ORGANIZED, 4, filter_mode="filter", filter_list="Day1,Day3"
        )
        assert not any("Day2" in k for k in result)

    def test_filter_mode_with_no_matches_returns_empty(self):
        result = pg.filter_folders_at_in_depth(
            self.ORGANIZED, 4, filter_mode="filter", filter_list="NonExistent"
        )
        assert result == {}

    def test_filter_mode_single_folder(self):
        result = pg.filter_folders_at_in_depth(
            self.ORGANIZED, 4, filter_mode="filter", filter_list="Day2"
        )
        assert len(result) == 1
        assert any("Day2" in k for k in result)

    def test_filter_mode_ignores_whitespace_around_names(self):
        result = pg.filter_folders_at_in_depth(
            self.ORGANIZED, 4, filter_mode="filter", filter_list=" Day1 , Day2 "
        )
        assert len(result) == 2

    def test_select_mode_all_returns_everything(self):
        with patch("builtins.input", return_value="all"):
            result = pg.filter_folders_at_in_depth(
                self.ORGANIZED, 4, filter_mode="select"
            )
        assert result == self.ORGANIZED

    def test_select_mode_single_index_selects_one_folder(self):
        # "1" selects the first item in sorted order
        sorted_keys = sorted(self.ORGANIZED.keys())
        with patch("builtins.input", return_value="1"):
            result = pg.filter_folders_at_in_depth(
                self.ORGANIZED, 4, filter_mode="select"
            )
        assert len(result) == 1
        assert sorted_keys[0] in result

    def test_select_mode_range_selects_multiple_folders(self):
        with patch("builtins.input", return_value="1-2"):
            result = pg.filter_folders_at_in_depth(
                self.ORGANIZED, 4, filter_mode="select"
            )
        assert len(result) == 2

    def test_select_mode_comma_separated_selection(self):
        with patch("builtins.input", return_value="1,3"):
            result = pg.filter_folders_at_in_depth(
                self.ORGANIZED, 4, filter_mode="select"
            )
        assert len(result) == 2
        sorted_keys = sorted(self.ORGANIZED.keys())
        assert sorted_keys[0] in result
        assert sorted_keys[2] in result


# ---------------------------------------------------------------------------
# is_json_file
# ---------------------------------------------------------------------------

class TestIsJsonFile:
    def test_dot_json_extension_returns_true(self):
        assert pg.is_json_file("/path/to/comparison.json") is True

    def test_dot_JSON_uppercase_returns_true(self):
        assert pg.is_json_file("/path/to/comparison.JSON") is True

    def test_non_json_nonexistent_path_returns_false(self):
        assert pg.is_json_file("/nonexistent/path/to/folder") is False

    def test_directory_path_returns_false(self):
        # os.path.isfile returns False for actual directories
        assert pg.is_json_file("/Volumes/SSD/Footage") is False

    def test_mov_extension_nonexistent_returns_false(self):
        assert pg.is_json_file("/nonexistent/clip.mov") is False
