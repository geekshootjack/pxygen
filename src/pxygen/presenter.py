"""Console presentation helpers for user-facing terminal output.

All output is plain text — no terminal UI dependency. Column alignment is
display-width aware (via :func:`display_width`) so full-width CJK text
lines up in any column, not just trailing ones.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Callable

OutputFn = Callable[[str], None]
# Receives the prompt string to display inline (like builtins.input)
InputFn = Callable[[str], str]


def display_width(text: str) -> int:
    """Return the terminal cell width of *text* (full-width CJK counts as 2)."""
    return sum(
        2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in text
    )


def pad_display(text: str, width: int) -> str:
    """Left-justify *text* to *width* terminal cells (display-width ljust)."""
    return text + " " * max(0, width - display_width(text))


def pad_display_right(text: str, width: int) -> str:
    """Right-justify *text* to *width* terminal cells (display-width rjust)."""
    return " " * max(0, width - display_width(text)) + text


class UserAbort(Exception):
    """Raised when the user enters 'q' at an interactive prompt."""


def prompt_line(input_func: InputFn, prompt: str = "> ") -> str:
    """Read one line of input; 'q' triggers a gentle program exit."""
    value = input_func(prompt).strip()
    if value.lower() == "q":
        raise UserAbort
    return value


def output_kv(title: str, pairs: list[tuple[str, object]], output: OutputFn) -> None:
    """Print a titled block of aligned key-value lines."""
    output(f"\n{title}")
    width = max(display_width(key) for key, _ in pairs)
    for key, value in pairs:
        output(f"  {pad_display(key, width)}  {value}")


def output_numbered(title: str, items: list[str], output: OutputFn) -> None:
    """Print a titled, numbered list (1-based)."""
    output(f"\n{title}")
    width = len(str(len(items)))
    for index, item in enumerate(items, 1):
        output(f"  {str(index).rjust(width)}  {item}")


class ConsolePresenter:
    """Render user-facing text without routing through logging."""

    def __init__(
        self,
        *,
        output_func: OutputFn | None = None,
        input_func: InputFn | None = None,
    ) -> None:
        self._output = output_func or print
        self._input = input_func or input

    def show(self, message: str) -> None:
        self._output(message)

    def read_line(self, prompt: str = "> ") -> str:
        return self._input(prompt)

    def confirm(self, prompt: str) -> bool:
        self.show(prompt)
        return prompt_line(self._input).lower() == "y"
