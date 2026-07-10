"""Tests for pxygen.presenter — prompts and gentle exit."""
from __future__ import annotations

import pytest

from pxygen.presenter import ConsolePresenter, UserAbort, prompt_line


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
