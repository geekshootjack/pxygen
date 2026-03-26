"""Tests for pxygen.paths."""
from pathlib import PurePosixPath

import pytest

from pxygen.paths import (
    clean_path_input,
    compute_key_path,
    is_json_file,
    path_parts,
)

# ---------------------------------------------------------------------------
# clean_path_input
# ---------------------------------------------------------------------------


class TestCleanPathInput:
    def test_removes_shell_escaped_space(self):
        assert clean_path_input("/path\\ with\\ spaces/file") == "/path with spaces/file"

    def test_removes_shell_escaped_hash(self):
        assert clean_path_input("/path\\#footage") == "/path#footage"

    def test_strips_surrounding_double_quotes(self):
        assert clean_path_input('"/Volumes/SSD/Footage"') == "/Volumes/SSD/Footage"

    def test_strips_surrounding_whitespace(self):
        assert clean_path_input("  /Volumes/SSD/Footage  ") == "/Volumes/SSD/Footage"

    def test_strips_quotes_and_whitespace_combined(self):
        assert clean_path_input('"  /Volumes/SSD/Footage  "') == "/Volumes/SSD/Footage"

    def test_normalizes_lowercase_windows_drive_letter(self):
        assert clean_path_input("c:/Users/footage") == "C:/Users/footage"

    def test_normalizes_lowercase_d_drive(self):
        assert clean_path_input("d:\\footage\\day1") == "D:\\footage\\day1"

    def test_leaves_uppercase_windows_drive_unchanged(self):
        assert clean_path_input("C:/Users/footage") == "C:/Users/footage"

    def test_unix_path_unchanged(self):
        assert clean_path_input("/Volumes/SSD/Footage") == "/Volumes/SSD/Footage"

    def test_shell_escape_and_quotes_combined(self):
        assert clean_path_input('"/path\\ with space"') == "/path with space"

    def test_non_windows_two_char_path_not_uppercased(self):
        assert clean_path_input("/a/footage") == "/a/footage"


# ---------------------------------------------------------------------------
# path_parts
# ---------------------------------------------------------------------------


class TestPathParts:
    def test_unix_absolute_path(self):
        result = path_parts("/Volumes/SSD/Footage/Day1")
        assert result == ["Volumes", "SSD", "Footage", "Day1"]

    def test_strips_leading_separator(self):
        result = path_parts("/a/b/c")
        assert result[0] != "/"
        assert result == ["a", "b", "c"]

    def test_empty_string_returns_empty(self):
        assert path_parts("") == []

    def test_single_component(self):
        result = path_parts("/Volumes")
        assert result == ["Volumes"]

    def test_depth_matches_expected(self):
        # A typical macOS footage path at 'CamA' level should have 5 components
        result = path_parts("/Volumes/SSD/Footage/Day1/CamA")
        assert len(result) == 5

    def test_windows_path_uses_windows_semantics_even_on_non_windows_host(self):
        result = path_parts(r"C:\Footage\Day1\CamA")
        assert result == ["C:", "Footage", "Day1", "CamA"]


# ---------------------------------------------------------------------------
# compute_key_path
# ---------------------------------------------------------------------------


class TestComputeKeyPath:
    def test_basic_depth(self):
        parts = ["Volumes", "SSD", "Footage", "Day1", "CamA"]
        result = compute_key_path(parts, 3, leading_sep=False)
        assert result == PurePosixPath("Volumes", "SSD", "Footage").as_posix()

    def test_windows_drive_letter_has_separator(self):
        parts = ["E:", "Footage", "Day1", "CamA"]
        result = compute_key_path(parts, 3, leading_sep=False)
        assert result == r"E:\Footage\Day1"

    def test_zero_depth_raises(self):
        with pytest.raises(ValueError):
            compute_key_path(["a", "b"], 0)

    def test_negative_depth_raises(self):
        with pytest.raises(ValueError):
            compute_key_path(["a", "b"], -1)

    def test_parts_shorter_than_depth_returns_none(self):
        assert compute_key_path(["Volumes", "SSD"], 5) is None

    def test_depth_equals_parts_length(self):
        parts = ["a", "b", "c"]
        result = compute_key_path(parts, 3, leading_sep=False)
        assert result == PurePosixPath("a", "b", "c").as_posix()

    def test_depth_one(self):
        result = compute_key_path(["Volumes", "SSD", "Footage"], 1, leading_sep=False)
        assert result == "Volumes"

    def test_leading_sep_true_adds_prefix(self):
        parts = ["Volumes", "SSD", "Footage"]
        result = compute_key_path(parts, 3, leading_sep=True)
        assert result == PurePosixPath("/", "Volumes", "SSD", "Footage").as_posix()

    def test_leading_sep_false_no_prefix(self):
        parts = ["Volumes", "SSD", "Footage"]
        result = compute_key_path(parts, 2, leading_sep=False)
        assert result == PurePosixPath("Volumes", "SSD").as_posix()

    def test_no_double_separator(self):
        parts = ["Volumes", "SSD"]
        result = compute_key_path(parts, 1, leading_sep=True)
        assert result == PurePosixPath("/", "Volumes").as_posix()


# ---------------------------------------------------------------------------
# is_json_file
# ---------------------------------------------------------------------------


class TestIsJsonFile:
    def test_dot_json_extension(self):
        assert is_json_file("/path/to/comparison.json") is True

    def test_dot_JSON_uppercase(self):
        assert is_json_file("/path/to/comparison.JSON") is True

    def test_nonexistent_non_json_path(self):
        assert is_json_file("/nonexistent/path/folder") is False

    def test_nonexistent_mov_path(self):
        assert is_json_file("/nonexistent/clip.mov") is False
