"""Console presentation helpers for user-facing terminal output."""
from __future__ import annotations

from collections.abc import Callable

from .table_output import OutputFn, output_table

# Receives the prompt string to display inline (like builtins.input)
InputFn = Callable[[str], str]


class ConsolePresenter:
    """Render user-facing text and tables without routing through logging."""

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

    def show_table(
        self,
        title: str,
        headers: tuple[str, ...],
        rows: list[tuple[object, ...]],
    ) -> None:
        output_table(title, headers, rows, self.show)

    def read_line(self, prompt: str = "> ") -> str:
        return self._input(prompt)

    def confirm(self, prompt: str) -> bool:
        self.show(prompt)
        return self.read_line().strip().lower() == "y"
