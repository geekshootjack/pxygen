"""Console presentation helpers for user-facing terminal output.

All output is plain text built with f-string alignment — no terminal UI
dependency. CJK-safe because wide characters only ever appear in trailing
columns (paths and folder names).
"""
from __future__ import annotations

from collections.abc import Callable

OutputFn = Callable[[str], None]
# Receives the prompt string to display inline (like builtins.input)
InputFn = Callable[[str], str]


def output_kv(title: str, pairs: list[tuple[str, object]], output: OutputFn) -> None:
    """Print a titled block of aligned key-value lines."""
    output(f"\n{title}")
    width = max(len(key) for key, _ in pairs)
    for key, value in pairs:
        output(f"  {key.ljust(width)}  {value}")


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
        return self.read_line().strip().lower() == "y"
