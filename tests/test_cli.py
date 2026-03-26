"""Tests for davinci_proxy_generator.cli — argument parsing and dispatch."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from davinci_proxy_generator.cli import _build_parser, main

# ---------------------------------------------------------------------------
# _build_parser — flag parsing
# ---------------------------------------------------------------------------


class TestParser:
    def _parse(self, argv):
        return _build_parser().parse_args(argv)

    def test_input_and_output(self):
        args = self._parse(["-i", "/footage", "-o", "/proxy"])
        assert args.input == "/footage"
        assert args.output == "/proxy"

    def test_long_input_output(self):
        args = self._parse(["--input", "/footage", "--output", "/proxy"])
        assert args.input == "/footage"
        assert args.output == "/proxy"

    def test_in_depth_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-n", "3"])
        assert args.in_depth == 3

    def test_out_depth_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-d", "6"])
        assert args.out_depth == 6

    def test_group_short(self):
        args = self._parse(["-i", "comp.json", "-o", "/p", "-g", "2"])
        assert args.group == 2

    def test_group_invalid_raises(self):
        with pytest.raises(SystemExit):
            self._parse(["-i", "comp.json", "-o", "/p", "-g", "3"])

    def test_filter_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-f", "Day1,Day2"])
        assert args.filter == "Day1,Day2"

    def test_select_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-s"])
        assert args.select is True

    def test_select_and_filter_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            self._parse(["-i", "/f", "-o", "/p", "-s", "-f", "Day1"])

    def test_clean_image_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-c"])
        assert args.clean_image is True

    def test_codec_short(self):
        args = self._parse(["-i", "/f", "-o", "/p", "-k", "prores"])
        assert args.codec == "prores"

    def test_codec_invalid_raises(self):
        with pytest.raises(SystemExit):
            self._parse(["-i", "/f", "-o", "/p", "-k", "vp9"])

    def test_defaults(self):
        import platform
        args = self._parse(["-i", "/f", "-o", "/p"])
        expected_depth = 5 if platform.system() == "Darwin" else 4
        assert args.in_depth == expected_depth
        assert args.out_depth == expected_depth
        assert args.group == 1
        assert args.codec == "auto"
        assert args.clean_image is False
        assert args.select is False
        assert args.filter is None


# ---------------------------------------------------------------------------
# main() — dispatch logic
# ---------------------------------------------------------------------------

_MOCK_DIR = "davinci_proxy_generator.cli.process_directory_mode"
_MOCK_JSON = "davinci_proxy_generator.cli.process_json_mode"


class TestDispatch:
    def _run(self, argv):
        with patch("sys.argv", ["proxy-generator"] + argv):
            main()

    def test_directory_mode_dispatched(self, tmp_path):
        footage = tmp_path / "footage"
        footage.mkdir()
        with patch(_MOCK_DIR) as mock_dir, patch(_MOCK_JSON) as mock_json:
            self._run(["-i", str(footage), "-o", "/proxy"])
            mock_dir.assert_called_once()
            mock_json.assert_not_called()

    def test_json_mode_dispatched(self, tmp_path):
        json_file = tmp_path / "comparison.json"
        json_file.write_text("{}")
        with patch(_MOCK_DIR) as mock_dir, patch(_MOCK_JSON) as mock_json:
            self._run(["-i", str(json_file), "-o", "/proxy"])
            mock_json.assert_called_once()
            mock_dir.assert_not_called()

    def test_json_detected_by_extension(self, tmp_path):
        # File doesn't need to exist — .json extension is enough
        json_path = "/nonexistent/comparison.json"
        with patch(_MOCK_DIR) as mock_dir, patch(_MOCK_JSON) as mock_json:
            self._run(["-i", json_path, "-o", "/proxy"])
            mock_json.assert_called_once()
            mock_dir.assert_not_called()

    def test_missing_output_exits(self, tmp_path):
        footage = tmp_path / "footage"
        footage.mkdir()
        with pytest.raises(SystemExit):
            self._run(["-i", str(footage)])

    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            self._run([])

    def test_group_passed_to_json_mode(self, tmp_path):
        json_path = "/nonexistent/comp.json"
        with patch(_MOCK_JSON) as mock_json:
            self._run(["-i", json_path, "-o", "/proxy", "-g", "2"])
            _, call_kwargs = mock_json.call_args
            assert mock_json.call_args[0][2] == 2  # group is 3rd positional arg

    def test_codec_passed_through(self, tmp_path):
        footage = tmp_path / "footage"
        footage.mkdir()
        with patch(_MOCK_DIR) as mock_dir:
            self._run(["-i", str(footage), "-o", "/proxy", "-k", "prores"])
            _, kwargs = mock_dir.call_args
            assert kwargs["codec"] == "prores"

    def test_clean_image_passed_through(self, tmp_path):
        footage = tmp_path / "footage"
        footage.mkdir()
        with patch(_MOCK_DIR) as mock_dir:
            self._run(["-i", str(footage), "-o", "/proxy", "-c"])
            _, kwargs = mock_dir.call_args
            assert kwargs["clean_image"] is True

    def test_legacy_positional_directory(self, tmp_path):
        footage = tmp_path / "footage"
        footage.mkdir()
        with patch(_MOCK_DIR) as mock_dir, patch(_MOCK_JSON) as mock_json:
            self._run([str(footage), "/proxy"])
            mock_dir.assert_called_once()
            mock_json.assert_not_called()

    def test_legacy_positional_json(self):
        json_path = "/nonexistent/comp.json"
        with patch(_MOCK_DIR) as mock_dir, patch(_MOCK_JSON) as mock_json:
            self._run([json_path, "/proxy"])
            mock_json.assert_called_once()
            mock_dir.assert_not_called()
