"""Shared terminal rendering helpers (tables and stage rules)."""
from __future__ import annotations

import io
import shutil
from collections.abc import Callable

from rich import box
from rich.console import Console, RenderableType
from rich.rule import Rule
from rich.table import Table

OutputFn = Callable[[str], None]


def _output_renderable(renderable: RenderableType, output: OutputFn) -> None:
    """Render a rich renderable to plain text through the output callback."""
    terminal_width = max(shutil.get_terminal_size(fallback=(160, 20)).columns, 120)
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=terminal_width,
        color_system=None,
        force_terminal=False,
        soft_wrap=False,
        legacy_windows=False,
    )
    console.print(renderable)
    for line in buffer.getvalue().splitlines():
        output(line)


def output_rule(title: str, output: OutputFn) -> None:
    """Render a titled horizontal rule marking a new interaction stage."""
    output("")
    _output_renderable(Rule(title, characters="─", style=""), output)


def output_table(
    title: str,
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
    output: OutputFn,
) -> None:
    """Render a plain-text rich table through the provided output callback."""
    output(f"\n{title}")
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="", expand=False)
    for index, header in enumerate(headers):
        kwargs = {}
        if index == 0:
            kwargs["justify"] = "right"
            kwargs["no_wrap"] = True
        elif header in {"Items", "Sub-folders", "Clips"}:
            kwargs["justify"] = "right"
            kwargs["no_wrap"] = True
        elif header == "Parameter":
            kwargs["no_wrap"] = True
        table.add_column(str(header), **kwargs)

    for row in rows:
        table.add_row(*(str(cell).replace("\n", " ") for cell in row))

    _output_renderable(table, output)
