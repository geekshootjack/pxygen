"""Tests for davinci_proxy_generator.organize."""

from davinci_proxy_generator.organize import (
    describe_folders_at_in_depth,
    filter_folders_at_in_depth,
    organize_directory_mode_folders,
    organize_json_mode_files,
    parse_selection,
    select_folders_at_in_depth,
)

# ---------------------------------------------------------------------------
# parse_selection
# ---------------------------------------------------------------------------


class TestParseSelection:
    def test_single_number(self):
        assert parse_selection("1", 5) == [0]

    def test_single_number_last_item(self):
        assert parse_selection("5", 5) == [4]

    def test_range(self):
        assert parse_selection("2-4", 5) == [1, 2, 3]

    def test_full_range(self):
        assert parse_selection("1-3", 3) == [0, 1, 2]

    def test_comma_separated(self):
        assert parse_selection("1,3,5", 5) == [0, 2, 4]

    def test_mixed_range_and_single(self):
        assert parse_selection("1,3,5-7", 10) == [0, 2, 4, 5, 6]

    def test_duplicates_removed(self):
        assert parse_selection("1,1,2", 5) == [0, 1]

    def test_result_is_sorted(self):
        assert parse_selection("3,1,2", 5) == [0, 1, 2]

    def test_out_of_range_ignored(self):
        assert parse_selection("6", 5) == []

    def test_zero_ignored(self):
        assert parse_selection("0", 5) == []

    def test_invalid_string_ignored(self):
        assert parse_selection("abc", 5) == []

    def test_empty_string(self):
        assert parse_selection("", 5) == []

    def test_whitespace_around_numbers(self):
        assert parse_selection(" 1 , 2 ", 5) == [0, 1]

    def test_malformed_range_ignored(self):
        assert parse_selection("1-", 5) == []


# ---------------------------------------------------------------------------
# organize_json_mode_files
# ---------------------------------------------------------------------------


class TestOrganizeJsonModeFiles:
    FILES = [
        "/Volumes/SSD/Footage/Day1/CamA/clip1.mov",
        "/Volumes/SSD/Footage/Day1/CamA/clip2.mov",
        "/Volumes/SSD/Footage/Day1/CamB/clip3.mov",
        "/Volumes/SSD/Footage/Day2/CamA/clip4.mov",
    ]

    def test_groups_by_cam_level_depth_5(self):
        result = organize_json_mode_files(self.FILES, in_depth=5, out_depth=5)
        assert len(result) == 3  # Day1/CamA, Day1/CamB, Day2/CamA

    def test_groups_by_day_level_depth_4(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        assert len(result) == 2  # Day1, Day2

    def test_subfolder_key_empty_when_depths_equal(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        for key_path in result:
            assert "" in result[key_path]

    def test_subfolder_key_populated_when_out_greater(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=5)
        day1_key = next(k for k in result if "Day1" in k)
        assert "CamA" in result[day1_key]
        assert "CamB" in result[day1_key]

    def test_correct_files_in_day1_group(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        day1_key = next(k for k in result if "Day1" in k)
        files = result[day1_key][""]
        assert "/Volumes/SSD/Footage/Day1/CamA/clip1.mov" in files
        assert "/Volumes/SSD/Footage/Day1/CamA/clip2.mov" in files
        assert "/Volumes/SSD/Footage/Day1/CamB/clip3.mov" in files
        assert "/Volumes/SSD/Footage/Day2/CamA/clip4.mov" not in files

    def test_correct_files_in_day2_group(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=4)
        day2_key = next(k for k in result if "Day2" in k)
        assert len(result[day2_key][""]) == 1
        assert "/Volumes/SSD/Footage/Day2/CamA/clip4.mov" in result[day2_key][""]

    def test_files_shallower_than_depth_skipped(self):
        assert organize_json_mode_files(["/a/b.mov"], in_depth=5, out_depth=5) == {}

    def test_empty_list(self):
        assert organize_json_mode_files([], in_depth=4, out_depth=4) == {}

    def test_multiple_files_same_subfolder(self):
        result = organize_json_mode_files(self.FILES, in_depth=4, out_depth=5)
        day1_key = next(k for k in result if "Day1" in k)
        cam_a_files = result[day1_key]["CamA"]
        assert len(cam_a_files) == 2


# ---------------------------------------------------------------------------
# organize_directory_mode_folders
# ---------------------------------------------------------------------------


class TestOrganizeDirectoryModeFolders:
    FOLDERS = [
        "/Volumes/SSD/Footage/Day1",
        "/Volumes/SSD/Footage/Day2",
        "/Volumes/SSD/Footage/Day3",
    ]

    def test_each_folder_becomes_own_key(self):
        result = organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        assert len(result) == 3

    def test_subfolder_key_always_empty(self):
        result = organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        for key_path in result:
            assert list(result[key_path].keys()) == [""]

    def test_folder_stored_as_single_item_list(self):
        result = organize_directory_mode_folders(self.FOLDERS, in_depth=4)
        day1_key = next(k for k in result if "Day1" in k)
        assert result[day1_key][""] == ["/Volumes/SSD/Footage/Day1"]

    def test_shallower_folders_skipped(self):
        assert organize_directory_mode_folders(["/a/b"], in_depth=5) == {}

    def test_empty_list(self):
        assert organize_directory_mode_folders([], in_depth=4) == {}


# ---------------------------------------------------------------------------
# filter_folders_at_in_depth
# ---------------------------------------------------------------------------


class TestFilterFoldersAtInDepth:
    ORGANIZED = {
        "/Volumes/SSD/Footage/Day1": {"": ["/Volumes/SSD/Footage/Day1"]},
        "/Volumes/SSD/Footage/Day2": {"": ["/Volumes/SSD/Footage/Day2"]},
        "/Volumes/SSD/Footage/Day3": {"": ["/Volumes/SSD/Footage/Day3"]},
    }

    def test_no_filter_returns_unchanged(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, None)
        assert result == self.ORGANIZED

    def test_filter_mode_keeps_matches(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, "Day1,Day3")
        assert len(result) == 2
        assert any("Day1" in k for k in result)
        assert any("Day3" in k for k in result)

    def test_filter_mode_excludes_non_matches(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, "Day1,Day3")
        assert not any("Day2" in k for k in result)

    def test_filter_mode_no_matches_returns_empty(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, "NonExistent")
        assert result == {}

    def test_filter_mode_single_folder(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, "Day2")
        assert len(result) == 1
        assert any("Day2" in k for k in result)

    def test_filter_mode_ignores_whitespace(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, " Day1 , Day2 ")
        assert len(result) == 2

    def test_none_filter_string_returns_unchanged(self):
        result = filter_folders_at_in_depth(self.ORGANIZED, None)
        assert result == self.ORGANIZED

    def test_describe_folders_at_in_depth_uses_folder_name_labels_by_default(self):
        options = describe_folders_at_in_depth(self.ORGANIZED)
        assert [option.label for option in options] == ["Day1", "Day2", "Day3"]

    def test_describe_folders_at_in_depth_can_use_full_paths(self):
        options = describe_folders_at_in_depth(self.ORGANIZED, show_full_path=True)
        assert options[0].label == "/Volumes/SSD/Footage/Day1"

    def test_select_folders_at_in_depth_single_index(self):
        sorted_keys = sorted(self.ORGANIZED.keys())
        result = select_folders_at_in_depth(self.ORGANIZED, [0])
        assert len(result) == 1
        assert sorted_keys[0] in result

    def test_select_folders_at_in_depth_multiple_indices(self):
        sorted_keys = sorted(self.ORGANIZED.keys())
        result = select_folders_at_in_depth(self.ORGANIZED, [0, 2])
        assert len(result) == 2
        assert sorted_keys[0] in result
        assert sorted_keys[2] in result
