"""Tests for pxygen.presenter — prompts, gentle exit, CJK-aware alignment."""
from __future__ import annotations

import pytest

from pxygen.presenter import (
    ConsolePresenter,
    UserAbort,
    display_width,
    output_kv,
    pad_display,
    pad_display_right,
    prompt_line,
)


class TestDisplayWidth:
    def test_ascii_counts_one_cell_per_char(self):
        assert display_width("Footage") == 7

    def test_cjk_counts_two_cells_per_char(self):
        assert display_width("素材") == 4

    def test_mixed_text(self):
        assert display_width("素材 Day1") == 9

    def test_pad_display_fills_to_cell_width(self):
        assert pad_display("素材", 6) == "素材  "
        assert pad_display_right("素材", 6) == "  素材"

    def test_pad_display_never_truncates(self):
        assert pad_display("素材根目录", 2) == "素材根目录"


class TestOutputKv:
    def test_mixed_width_keys_align_values_to_same_cell_column(self):
        lines: list[str] = []
        output_kv("标题", [("素材", "v1"), ("ab", "v2")], lines.append)

        value_columns = {
            display_width(line.split("v")[0]) for line in lines if "v" in line
        }
        assert len(value_columns) == 1


class TestPromptLine:
    def test_returns_stripped_input(self):
        assert prompt_line(lambda _: "  all  ") == "all"

    def test_q_raises_user_abort(self):
        with pytest.raises(UserAbort):
            prompt_line(lambda _: "q")

    def test_q_is_case_insensitive(self):
        with pytest.raises(UserAbort):
            prompt_line(lambda _: " Q ")


class TestConfirm:
    def test_y_confirms(self):
        presenter = ConsolePresenter(output_func=lambda _: None, input_func=lambda _: "y")
        assert presenter.confirm("go? (y/n/q)") is True

    def test_n_declines(self):
        presenter = ConsolePresenter(output_func=lambda _: None, input_func=lambda _: "n")
        assert presenter.confirm("go? (y/n/q)") is False

    def test_q_raises_user_abort(self):
        presenter = ConsolePresenter(output_func=lambda _: None, input_func=lambda _: "q")
        with pytest.raises(UserAbort):
            presenter.confirm("go? (y/n/q)")
